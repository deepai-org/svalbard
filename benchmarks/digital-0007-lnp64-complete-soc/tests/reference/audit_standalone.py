#!/usr/bin/env python3
"""Reject host-local dependencies and unapproved external references."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {
    ".json", ".md", ".py", ".s", ".sdc", ".sh", ".sv", ".tcl", ".toml", ".v"
}
FORBIDDEN = (
    "." * 2 + "/",
    "/" + "home/",
    "/" + "Users/",
    "file" + "://",
    "git" + "@",
    "local" + "host",
    "127" + ".0.0.1",
)
PUBLIC_URLS = {
    "http://www.apache.org/licenses/",
    "http://www.apache.org/licenses/LICENSE-2.0",
    "https://creativecommons.org/licenses/by/4.0/.",
    "https://github.com/deepai-org/gf180mcu-kianv-rv32ima-sv32.git",
    "https://github.com/fossi-foundation/open-pdks.git",
    "https://github.com/google/gf180mcu-pdk.git",
    "https://github.com/wyvernSemi/pcievhost.git",
    "https://github.com/wyvernSemi/vproc.git",
    "https://hub.docker.com/r/hpretl/iic-osic-tools",
}


def main() -> None:
    links = set()
    for path in ROOT.rglob("*"):
        if path.is_symlink():
            raise SystemExit(f"symlink is not standalone: {path.relative_to(ROOT)}")
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(errors="strict")
        for token in FORBIDDEN:
            if token in text:
                raise SystemExit(f"host-local reference {token!r} in {path.relative_to(ROOT)}")
        links.update(re.findall(r"https?://[^\s\"'<>`)]+", text))
    unexpected = links - PUBLIC_URLS
    if unexpected:
        raise SystemExit(f"unapproved external URLs: {sorted(unexpected)}")
    print("standalone dependency audit: PASS")


if __name__ == "__main__":
    main()
