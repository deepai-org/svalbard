#!/usr/bin/env python3
"""Deterministically lower role-specific receiver variants from one template."""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
VARIANTS = {
    "capture": {},
    "sense": {
        "XGAIN A MIDP VDD VSS rlr_inv WP=8u WN=6u MP=2 MN=2":
            "XGAIN A MIDP VDD VSS rlr_inv WP=8u WN=6u MP=4 MN=4",
        "XOUTN MIDP OUTN VDD VSS rlr_inv WP=8u WN=6u MP=3 MN=2":
            "XOUTN MIDP OUTN VDD VSS rlr_inv WP=8u WN=6u MP=6 MN=4",
        "{XGAIN_N nfet_03v3 6 2 -38 18 MIDP A VSS}":
            "{XGAIN_N nfet_03v3 6 4 -38 18 MIDP A VSS}",
        "{XOUTN_N nfet_03v3 6 2 40 18 OUTN MIDP VSS}":
            "{XOUTN_N nfet_03v3 6 4 40 18 OUTN MIDP VSS}",
        "{XGAIN_P pfet_03v3 8 2 -38 58 MIDP A VDD}":
            "{XGAIN_P pfet_03v3 8 4 -38 58 MIDP A VDD}",
        "{XOUTN_P pfet_03v3 8 3 40 58 OUTN MIDP VDD}":
            "{XOUTN_P pfet_03v3 8 6 40 58 OUTN MIDP VDD}",
    },
}
VARIANTS["sense_fast"] = {
    **VARIANTS["sense"],
    "XDNL VSS VSS VSS VSS nfet_03v3 w=8u":
        "XDNL VSS VSS VSS VSS nfet_03v3 w=12u",
    "XIS N1 IN TAIL VSS nfet_03v3 w=8u":
        "XIS N1 IN TAIL VSS nfet_03v3 w=12u",
    "XIR N2 REF TAIL VSS nfet_03v3 w=8u":
        "XIR N2 REF TAIL VSS nfet_03v3 w=12u",
    "XDNR VSS VSS VSS VSS nfet_03v3 w=8u":
        "XDNR VSS VSS VSS VSS nfet_03v3 w=12u",
    "XTAIL TAIL VBIAS VSS VSS nfet_03v3 w=12u":
        "XTAIL TAIL VBIAS VSS VSS nfet_03v3 w=18u",
    "XPL N1 N1 VDD VDD pfet_03v3 w=8u":
        "XPL N1 N1 VDD VDD pfet_03v3 w=12u",
    "XPR N2 N1 VDD VDD pfet_03v3 w=8u":
        "XPR N2 N1 VDD VDD pfet_03v3 w=12u",
    "XDPL VDD VDD VDD VDD pfet_03v3 w=8u":
        "XDPL VDD VDD VDD VDD pfet_03v3 w=12u",
    "XDPR VDD VDD VDD VDD pfet_03v3 w=8u":
        "XDPR VDD VDD VDD VDD pfet_03v3 w=12u",
    "{XDNL nfet_03v3 8 1": "{XDNL nfet_03v3 12 1",
    "{XIS nfet_03v3 8 1": "{XIS nfet_03v3 12 1",
    "{XIR nfet_03v3 8 1": "{XIR nfet_03v3 12 1",
    "{XDNR nfet_03v3 8 1": "{XDNR nfet_03v3 12 1",
    "{XTAIL nfet_03v3 12 2": "{XTAIL nfet_03v3 18 2",
    "{XDPL pfet_03v3 8 1": "{XDPL pfet_03v3 12 1",
    "{XPL pfet_03v3 8 1": "{XPL pfet_03v3 12 1",
    "{XPR pfet_03v3 8 1": "{XPR pfet_03v3 12 1",
    "{XDPR pfet_03v3 8 1": "{XDPR pfet_03v3 12 1",
}
VARIANTS["sense_schmitt"] = {
    **VARIANTS["sense"],
    "XISO N2 A VDD VSS rlr_inv WP=4u WN=2u MP=1 MN=1": """XISOP1 PINT N2 VDD VDD pfet_03v3 w=4u l=0.28u m=1
XISOP2 A N2 PINT VDD pfet_03v3 w=4u l=0.28u m=1
XISOPF PINT A VDD VDD pfet_03v3 w=4u l=0.28u m=1
XISON1 A N2 NINT VSS nfet_03v3 w=2u l=0.28u m=1
XISON2 NINT N2 VSS VSS nfet_03v3 w=2u l=0.28u m=1
XISONF NINT A VSS VSS nfet_03v3 w=2u l=0.28u m=1""",
}


def digest(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def transform(text: str, variant: str, domain: str) -> str:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant}")
    for old, new in VARIANTS[variant].items():
        if (domain == "spice") != old.startswith("X"):
            continue
        if old not in text:
            raise ValueError(f"variant anchor missing: {old}")
        text = text.replace(old, new)
    return text


def compile_spice(variant: str, top: str) -> str:
    text = transform((HERE / "reference_level_receiver.spice").read_text(), variant,
                     "spice")
    text = text.replace(".subckt reference_level_receiver IN", f".subckt {top} IN", 1)
    text = text.replace(".ends reference_level_receiver", f".ends {top}", 1)
    return text


def compile_layout(variant: str, top: str) -> str:
    text = transform((HERE / "layout.tcl").read_text(), variant, "layout")
    return text.replace("reference_level_receiver", top)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=VARIANTS, required=True)
    parser.add_argument("--top", required=True)
    parser.add_argument("--spice-output", required=True, type=Path)
    parser.add_argument("--layout-output", type=Path)
    parser.add_argument("--manifest-output", required=True, type=Path)
    args = parser.parse_args()
    spice = compile_spice(args.variant, args.top)
    layout = compile_layout(args.variant, args.top) if args.layout_output else None
    args.spice_output.write_text(spice)
    if args.layout_output:
        args.layout_output.write_text(layout)
    manifest = {"schema_version": 1, "variant": args.variant, "top": args.top,
                "spice_sha256": digest(spice),
                "layout_sha256": digest(layout) if layout is not None else None,
                "compiler_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.manifest_output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
