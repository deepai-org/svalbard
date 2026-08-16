#!/usr/bin/env python3
"""Validate and expose immutable image references without shell evaluation."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
NAME = re.compile(r"^[a-z0-9][a-z0-9./_-]*$")
PULLABLE_STATES = {"metadata_verified", "version_probe_passed", "qualified"}


def pull_list() -> None:
    lock = json.loads((ROOT / "env/images.lock").read_text())
    references: list[str] = []
    for image in lock["images"]:
        name = image.get("name", "")
        digest = image.get("digest", "")
        if image.get("platform") != "linux/arm64":
            raise SystemExit(f"image {image.get('role')} is not locked to linux/arm64")
        if image.get("status") not in PULLABLE_STATES:
            raise SystemExit(f"image {image.get('role')} metadata is not reviewed for pulling")
        if not NAME.fullmatch(name) or not DIGEST.fullmatch(digest):
            raise SystemExit(f"image {image.get('role')} has an unsafe or incomplete reference")
        references.append(f"{name}@{digest}")
    if not references:
        raise SystemExit("image lock contains no pullable images")
    print("\n".join(references))


def main() -> None:
    if sys.argv[1:] != ["pull-list"]:
        raise SystemExit("usage: image_lock.py pull-list")
    pull_list()


if __name__ == "__main__":
    main()
