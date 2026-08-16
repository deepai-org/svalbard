#!/usr/bin/env python3
"""Fetch and safely materialize checksum-locked verification source archives."""

from __future__ import annotations

import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "projects/pcie_gen1_endpoint/verification/dependencies.lock"
CACHE = ROOT / "scratch/verification-deps"
ALLOWED_HOSTS = {"codeload.github.com", "files.pythonhosted.org"}
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
SAFE_ID = re.compile(r"^[a-z0-9_.-]+$")


def fail(message: str) -> None:
    raise SystemExit(f"verification-deps: {message}")


def entries() -> list[dict]:
    document = json.loads(LOCK.read_text(encoding="utf-8"))
    result = [item for item in document["dependencies"] if "archive_url" in item]
    total = 0
    for item in result:
        if not SAFE_ID.fullmatch(item["id"]):
            fail(f"unsafe dependency ID: {item['id']!r}")
        if urllib.parse.urlparse(item["archive_url"]).hostname not in ALLOWED_HOSTS:
            fail(f"unapproved archive host for {item['id']}")
        size = item["archive_bytes"]
        if not isinstance(size, int) or not 0 < size <= MAX_ARCHIVE_BYTES:
            fail(f"invalid archive size for {item['id']}")
        if not re.fullmatch(r"[0-9a-f]{64}", item["archive_sha256"]):
            fail(f"invalid SHA-256 for {item['id']}")
        total += size
    if total > MAX_TOTAL_BYTES:
        fail("locked archive total exceeds the 100 MiB safety ceiling")
    return result


def archive_path(item: dict) -> Path:
    return CACHE / f"{item['id']}-{item['archive_sha256']}.tar.gz"


def verify(path: Path, item: dict) -> None:
    if not path.is_file():
        fail(f"missing archive for {item['id']}; run fetch first")
    if path.stat().st_size != item["archive_bytes"]:
        fail(f"size mismatch for {item['id']}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != item["archive_sha256"]:
        fail(f"checksum mismatch for {item['id']}")


def fetch() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    with (CACHE / ".fetch.lock").open("w") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        for item in entries():
            destination = archive_path(item)
            if destination.exists():
                verify(destination, item)
                print(f"cached {item['id']}")
                continue
            with tempfile.NamedTemporaryFile(dir=CACHE, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                try:
                    request = urllib.request.Request(
                        item["archive_url"], headers={"User-Agent": "svalbard-verification-deps/1"}
                    )
                    with urllib.request.urlopen(request, timeout=60) as response:
                        if urllib.parse.urlparse(response.url).hostname not in ALLOWED_HOSTS:
                            fail(f"redirected to unapproved archive host for {item['id']}")
                        while chunk := response.read(1024 * 1024):
                            temporary.write(chunk)
                            if temporary.tell() > item["archive_bytes"]:
                                fail(f"oversized response for {item['id']}")
                    temporary.flush()
                    verify(temporary_path, item)
                    temporary_path.replace(destination)
                finally:
                    temporary_path.unlink(missing_ok=True)
            print(f"fetched {item['id']} ({item['archive_bytes']} bytes)")


def materialize(destination: Path) -> None:
    if destination.exists():
        fail(f"materialize destination already exists: {destination}")
    destination.mkdir(parents=True)
    try:
        for item in entries():
            source = archive_path(item)
            verify(source, item)
            target = destination / item["id"]
            target.mkdir()
            with tarfile.open(source, mode="r:gz") as archive:
                members = archive.getmembers()
                if not members:
                    fail(f"empty archive for {item['id']}")
                prefix = members[0].name.split("/", 1)[0]
                for member in members:
                    parts = Path(member.name).parts
                    if not parts or parts[0] != prefix or ".." in parts:
                        fail(f"unsafe archive member for {item['id']}: {member.name}")
                    member.name = str(Path(*parts[1:]))
                    if not member.name or member.issym() or member.islnk() or member.isdev():
                        continue
                    archive.extract(member, target, filter="data")
            print(f"materialized {item['id']} -> {target}")
    except BaseException:
        shutil.rmtree(destination)
        raise


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "fetch":
        fetch()
    elif len(sys.argv) == 3 and sys.argv[1] == "materialize":
        materialize(Path(sys.argv[2]).resolve())
    elif len(sys.argv) == 2 and sys.argv[1] == "verify":
        for item in entries():
            verify(archive_path(item), item)
            print(f"verified {item['id']}")
    else:
        fail("usage: verification_deps.py {fetch|verify|materialize DEST}")


if __name__ == "__main__":
    main()
