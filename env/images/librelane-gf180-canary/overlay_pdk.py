#!/usr/bin/env python3
"""Apply and verify the narrow LibreLane 3 compatibility overlay."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path("/pdk/gf180mcuD/libs.tech/librelane")


def rewrite(
    path: Path,
    source_sha256: str,
    result_sha256: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> None:
    source = path.read_bytes()
    observed = hashlib.sha256(source).hexdigest()
    if observed != source_sha256:
        raise SystemExit(f"unexpected pristine PDK configuration hash for {path}: {observed}")
    text = source.decode("utf-8")
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    result = (text[:start] + replacement + text[end:]).encode("utf-8")
    observed_result = hashlib.sha256(result).hexdigest()
    if observed_result != result_sha256:
        raise SystemExit(f"unexpected compatibility overlay hash for {path}: {observed_result}")
    path.write_bytes(result)


rewrite(
    ROOT / "config.tcl",
    "962b8c36eb81f5ada2dc9f5359d3942370b22551df1ea80acbb5fb2a9c9151ed",
    "dfd52190eb043b290273ff7a4dabb2b7d582a5a30c374409679aa4d2ecc2b02d",
    "# Technology lib\n",
    "# Corners",
    """# LibreLane 3 compatibility names for the same locked Liberty files.
set ::env(LIB_SYNTH) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/$::env(STD_CELL_LIBRARY)/lib/$::env(STD_CELL_LIBRARY)__tt_025C_5v00.lib"
set ::env(LIB_FASTEST) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/$::env(STD_CELL_LIBRARY)/lib/$::env(STD_CELL_LIBRARY)__ff_n40C_5v50.lib"
set ::env(LIB_SLOWEST) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/$::env(STD_CELL_LIBRARY)/lib/$::env(STD_CELL_LIBRARY)__ss_125C_4v50.lib"

""",
)

rewrite(
    ROOT / "gf180mcu_fd_io/config.tcl",
    "d1a747c54e469741c2bdddbc07596eeadca01cf6bc427bdc5ef14c23cf6940d7",
    "ebc2c799800f0950668f295e769d36c78149383e3431a4b0f4672bd0f798563e",
    "# Technology lib\n",
    "# Pad cells",
    """# Pad timing is intentionally omitted by the core-only LibreLane 3 canary.

""",
)
