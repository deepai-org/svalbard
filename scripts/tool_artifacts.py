#!/usr/bin/env python3
"""Fetch and extract locked solver packages without installing them."""

from __future__ import annotations

import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "env/tool_artifacts.lock"
CACHE = ROOT / "scratch/tool-artifacts"
ALLOWED_HOSTS = {
    "github.com",
    "ports.ubuntu.com",
    "release-assets.githubusercontent.com",
}
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
SAFE = re.compile(r"^[A-Za-z0-9_.+:-]+$")


def fail(message: str) -> None:
    raise SystemExit(f"tool-artifacts: {message}")


def artifacts() -> list[dict]:
    document = json.loads(LOCK.read_text(encoding="utf-8"))
    result = document["artifacts"]
    total = 0
    for item in result:
        for field in ("id", "package", "version", "architecture"):
            if not SAFE.fullmatch(item[field]):
                fail(f"unsafe {field} for {item.get('id', '<unknown>')}")
        if item["architecture"] != "arm64":
            fail(f"unexpected architecture for {item['id']}")
        if item.get("format") not in {"deb", "tar_gzip_member"}:
            fail(f"unsupported format for {item['id']}")
        if urllib.parse.urlparse(item["url"]).hostname not in ALLOWED_HOSTS:
            fail(f"unapproved host for {item['id']}")
        if not isinstance(item["bytes"], int) or not 0 < item["bytes"] <= MAX_ARTIFACT_BYTES:
            fail(f"invalid size for {item['id']}")
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            fail(f"invalid SHA-256 for {item['id']}")
        total += item["bytes"]
    if total > MAX_TOTAL_BYTES:
        fail("artifact total exceeds the 32 MiB safety ceiling")
    return result


def artifact_path(item: dict) -> Path:
    suffix = ".deb" if item["format"] == "deb" else ".tgz"
    return CACHE / f"{item['id']}-{item['sha256']}{suffix}"


def tar_payload(path: Path, item: dict):
    member_name = item.get("member", "")
    if not member_name or member_name.startswith("/") or ".." in Path(member_name).parts:
        fail(f"unsafe archive member for {item['id']}")
    try:
        archive = tarfile.open(path, mode="r:gz")
        member = archive.getmember(member_name)
    except (KeyError, tarfile.TarError) as error:
        fail(f"invalid archive for {item['id']}: {error}")
    if not member.isfile() or member.size != item.get("payload_bytes"):
        archive.close()
        fail(f"unexpected archive payload for {item['id']}")
    payload = archive.extractfile(member)
    if payload is None:
        archive.close()
        fail(f"unreadable archive payload for {item['id']}")
    return archive, payload


def verify(path: Path, item: dict) -> None:
    if not path.is_file():
        fail(f"missing {item['id']}; run fetch first")
    if path.stat().st_size != item["bytes"]:
        fail(f"size mismatch for {item['id']}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        fail(f"checksum mismatch for {item['id']}")
    if item["format"] == "deb":
        observed = [
            subprocess.check_output(["dpkg-deb", "--field", path, field], text=True).strip()
            for field in ("Package", "Version", "Architecture")
        ]
        expected = [item["package"], item["version"], item["architecture"]]
        if observed != expected:
            fail(f"package metadata mismatch for {item['id']}: {observed!r}")
    else:
        archive, payload = tar_payload(path, item)
        try:
            digest = hashlib.sha256()
            while chunk := payload.read(1024 * 1024):
                digest.update(chunk)
            if digest.hexdigest() != item.get("payload_sha256"):
                fail(f"archive payload checksum mismatch for {item['id']}")
        finally:
            payload.close()
            archive.close()


def fetch() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    with (CACHE / ".fetch.lock").open("w") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        for item in artifacts():
            destination = artifact_path(item)
            if destination.exists():
                verify(destination, item)
                print(f"cached {item['id']}")
                continue
            with tempfile.NamedTemporaryFile(dir=CACHE, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                try:
                    request = urllib.request.Request(
                        item["url"], headers={"User-Agent": "svalbard-tool-artifacts/1"}
                    )
                    with urllib.request.urlopen(request, timeout=60) as response:
                        if urllib.parse.urlparse(response.url).hostname not in ALLOWED_HOSTS:
                            fail(f"redirected to unapproved host for {item['id']}")
                        while chunk := response.read(1024 * 1024):
                            temporary.write(chunk)
                            if temporary.tell() > item["bytes"]:
                                fail(f"oversized response for {item['id']}")
                    temporary.flush()
                    verify(temporary_path, item)
                    temporary_path.replace(destination)
                finally:
                    temporary_path.unlink(missing_ok=True)
            print(f"fetched {item['id']} ({item['bytes']} bytes)")


def materialize(destination: Path) -> None:
    if destination.exists():
        fail(f"materialize destination already exists: {destination}")
    destination.mkdir(parents=True)
    try:
        for item in artifacts():
            source = artifact_path(item)
            verify(source, item)
            if item["format"] == "deb":
                subprocess.run(["dpkg-deb", "--extract", source, destination], check=True)
            else:
                binary = destination / "usr/bin" / item["package"]
                binary.parent.mkdir(parents=True, exist_ok=True)
                archive, payload = tar_payload(source, item)
                try:
                    with binary.open("xb") as output:
                        shutil.copyfileobj(payload, output, length=1024 * 1024)
                    binary.chmod(0o755)
                finally:
                    payload.close()
                    archive.close()
            print(f"materialized {item['id']}")
    except BaseException:
        shutil.rmtree(destination)
        raise


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "fetch":
        fetch()
    elif len(sys.argv) == 2 and sys.argv[1] == "verify":
        for item in artifacts():
            verify(artifact_path(item), item)
            print(f"verified {item['id']}")
    elif len(sys.argv) == 3 and sys.argv[1] == "materialize":
        materialize(Path(sys.argv[2]).resolve())
    else:
        fail("usage: tool_artifacts.py {fetch|verify|materialize DEST}")


if __name__ == "__main__":
    main()
