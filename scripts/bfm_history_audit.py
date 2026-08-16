#!/usr/bin/env python3
"""Clone and compare full BFM histories up to the locked revisions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "scratch"
MINIMUM_FREE_BYTES = 100 * 1024**3
MINIMUM_AVAILABLE_MEMORY_BYTES = 8 * 1024**3
MAX_PROCESS_FILE_BYTES = 64 * 1024**2
SOURCE_SUFFIX = re.compile(rb"\.(c|cc|cpp|h|hpp|py|sv|v|vhd|vhdl)$", re.IGNORECASE)
REPOSITORIES = {
    "cocotbext_pcie": {
        "url": "https://github.com/alexforencich/cocotbext-pcie.git",
        "revision": "92732edd2d8cef002f0e984697ff31ccfe8a19a9",
        "opposite_pattern": "pcievhost|wyvernsemi|vproc",
    },
    "pcievhost": {
        "url": "https://github.com/wyvernSemi/pcievhost.git",
        "revision": "b82b2ff3a047f742354c9607dea34b9b97bf108c",
        "opposite_pattern": "cocotbext[-_. ]?pcie|alex forencich",
    },
}


def fail(message: str) -> None:
    raise SystemExit(f"bfm-history-audit: {message}")


def limit_file_size() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_PROCESS_FILE_BYTES, MAX_PROCESS_FILE_BYTES))


def git(git_dir: Path, *arguments: str) -> bytes:
    return subprocess.check_output(
        ["git", f"--git-dir={git_dir}", *arguments],
        stderr=subprocess.STDOUT,
        timeout=300,
        preexec_fn=limit_file_size,
    )


if len(sys.argv) != 2:
    fail("usage: bfm_history_audit.py OUTPUT_JSON")
output_path = Path(sys.argv[1]).resolve()
if output_path.exists():
    fail(f"output already exists: {output_path}")
if shutil.disk_usage(ROOT).free < MINIMUM_FREE_BYTES:
    fail("refusing below 100 GiB repository free space")
memory = {
    line.split(":", 1)[0]: int(line.split()[1]) * 1024
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
}
if memory.get("MemAvailable", 0) < MINIMUM_AVAILABLE_MEMORY_BYTES:
    fail("refusing below 8 GiB available memory")

SCRATCH.mkdir(exist_ok=True)
temporary = Path(tempfile.mkdtemp(prefix="bfm-history.", dir=SCRATCH))
try:
    observations = {}
    authors = {}
    blobs = {}
    for name, repository in REPOSITORIES.items():
        git_dir = temporary / f"{name}.git"
        subprocess.run(
            ["git", "init", "--quiet", "--bare", git_dir],
            check=True,
            timeout=300,
            preexec_fn=limit_file_size,
        )
        revision = repository["revision"]
        git(git_dir, "remote", "add", "origin", repository["url"])
        git(git_dir, "fetch", "--quiet", "origin", revision)
        git(git_dir, "cat-file", "-e", f"{revision}^{{commit}}")
        commits = git(git_dir, "rev-list", revision).splitlines()
        author_lines = git(git_dir, "log", "--format=%an <%ae>", revision).splitlines()
        authors[name] = {line.decode("utf-8", errors="replace").casefold() for line in author_lines}
        objects = git(git_dir, "rev-list", "--objects", revision).splitlines()
        blobs[name] = {
            line.split(b" ", 1)[0].decode("ascii")
            for line in objects
            if b" " in line and SOURCE_SUFFIX.search(line.split(b" ", 1)[1])
        }
        reference_commits = git(
            git_dir,
            "log",
            "--format=%H",
            "-i",
            "-G",
            repository["opposite_pattern"],
            revision,
        ).splitlines()
        observations[name] = {
            "revision": revision,
            "ancestor_commits": len(commits),
            "author_identities": len(authors[name]),
            "source_blob_objects": len(blobs[name]),
            "cross_project_reference_commits": len(reference_commits),
        }

    shared_authors = sorted(authors["cocotbext_pcie"] & authors["pcievhost"])
    shared_blobs = sorted(blobs["cocotbext_pcie"] & blobs["pcievhost"])
    cross_references = sum(item["cross_project_reference_commits"] for item in observations.values())
    if shared_authors or shared_blobs or cross_references:
        fail(
            "history comparison found shared authors, source blobs, or cross references: "
            f"authors={shared_authors}, blobs={shared_blobs}, references={cross_references}"
        )
    result = {
        "schema_version": 1,
        "result": "pass_with_limitations",
        "repositories": observations,
        "comparison": {
            "shared_author_identities": [],
            "shared_source_blob_objects": [],
            "cross_project_reference_commits": 0,
            "conclusion": "no shared lineage observed in full ancestor histories at the locked revisions",
        },
        "limitations": [
            "Git object identity and text/reference scans are evidence of distinct lineage, not proof of independent specification interpretation",
            "the remote transport is not used as a release input; executable source remains bound by the SHA-256 archive lock",
        ],
    }
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
finally:
    shutil.rmtree(temporary)

print("bfm-history-audit: PASS (full pinned-revision ancestry comparison)")
