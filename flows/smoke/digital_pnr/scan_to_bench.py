#!/usr/bin/env python3
import hashlib
import re
import sys
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"scan-to-bench: {message}")


if len(sys.argv) != 3:
    fail("usage: scan_to_bench.py NETLIST OUTPUT_BENCH")

netlist, output = map(Path, sys.argv[1:])
text = netlist.read_text()
if len(re.findall(r"\bmodule\s+counter\b", text)) != 1:
    fail("expected exactly one counter module")
if " assign " in text:
    fail("netlist must be normalized before conversion")


def declarations(kind: str) -> list[str]:
    names = []
    pattern = rf"\b{kind}\s+(?:wire\s+|reg\s+)?(?:\[(\d+):(\d+)\]\s+)?([^;]+);"
    for match in re.finditer(pattern, text):
        high, low, body = match.groups()
        for raw_name in body.split(","):
            name = raw_name.strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", name):
                fail(f"unsupported {kind} declaration {name!r}")
            if high is None:
                names.append(name)
            else:
                start, stop = int(high), int(low)
                step = -1 if start >= stop else 1
                names.extend(f"{name}[{bit}]" for bit in range(start, stop + step, step))
    return names


primary_inputs = [name for name in declarations("input") if name == "rst"]
primary_outputs = declarations("output")
if primary_inputs != ["rst"]:
    fail(f"expected functional primary input rst, found {primary_inputs!r}")
if sorted(primary_outputs) != ["count[0]", "count[1]", "count[2]", "count[3]", "scan_out_0"]:
    fail(f"unexpected primary outputs {primary_outputs!r}")


def encode(net: str) -> str:
    return "n_" + "".join(
        char if char.isalnum() or char == "_" else f"_{ord(char):02x}_" for char in net
    )


cell_pattern = re.compile(
    r"gf180mcu_fd_sc_mcu7t5v0__(?P<cell>[A-Za-z0-9_]+)\s+"
    r"(?P<instance>[A-Za-z_][A-Za-z0-9_$]*)\s*\((?P<ports>.*?)\);",
    re.DOTALL,
)
port_pattern = re.compile(r"\.(?P<port>[A-Za-z0-9_]+)\s*\(\s*(?P<net>[^()\s]+)\s*\)")
statements: list[str] = []
drivers: set[str] = set()
dependencies: set[str] = set()
scan_cells = 0


def add_statement(target: str, gate: str, inputs: list[str]) -> None:
    if target in drivers:
        fail(f"multiple drivers for {target}")
    drivers.add(target)
    dependencies.update(inputs)
    statements.append(f"{encode(target)} = {gate}({', '.join(map(encode, inputs))})")


for match in cell_pattern.finditer(text):
    raw_cell = match.group("cell")
    cell = re.sub(r"_\d+$", "", raw_cell)
    instance = match.group("instance")
    ports = {item.group("port"): item.group("net") for item in port_pattern.finditer(match.group("ports"))}
    if len(ports) != len(port_pattern.findall(match.group("ports"))):
        fail(f"duplicate ports on {instance}")

    if cell in {"buf", "dlyb"}:
        add_statement(ports["Z"], "BUF", [ports["I"]])
    elif cell == "inv":
        add_statement(ports["ZN"], "NOT", [ports["I"]])
    elif match_gate := re.fullmatch(r"(and|nand|or|nor|xor|xnor)([234])", cell):
        gate, width = match_gate.groups()
        pins = [f"A{index}" for index in range(1, int(width) + 1)]
        output_port = "Z" if gate in {"and", "or", "xor"} else "ZN"
        add_statement(ports[output_port], gate.upper(), [ports[pin] for pin in pins])
    elif cell == "aoi21":
        intermediate = f"__atpg_{instance}_and"
        add_statement(intermediate, "AND", [ports["A1"], ports["A2"]])
        add_statement(ports["ZN"], "NOR", [intermediate, ports["B"]])
    elif cell == "oai21":
        intermediate = f"__atpg_{instance}_or"
        add_statement(intermediate, "OR", [ports["A1"], ports["A2"]])
        add_statement(ports["ZN"], "NAND", [intermediate, ports["B"]])
    elif cell == "sdffq":
        add_statement(ports["Q"], "DFF", [ports["D"]])
        scan_cells += 1
    else:
        fail(f"unsupported cell {raw_cell} on {instance}")

if scan_cells != 4:
    fail(f"expected four scan cells, found {scan_cells}")
if len(statements) < 12:
    fail(f"unexpectedly small logic model: {len(statements)} gates")

available = drivers | set(primary_inputs)
unknown = sorted(dependencies - available)
if unknown:
    fail(f"undriven logic nets: {unknown}")
missing_outputs = sorted(set(primary_outputs) - available)
if missing_outputs:
    fail(f"undriven primary outputs: {missing_outputs}")

source_hash = hashlib.sha256(netlist.read_bytes()).hexdigest()
lines = [
    "# GF180 normalized scan netlist converted for full-scan ATPG",
    f"# source_sha256={source_hash}",
    *(f"INPUT({encode(name)})" for name in primary_inputs),
    *(f"OUTPUT({encode(name)})" for name in primary_outputs),
    *statements,
]
output.write_text("\n".join(lines) + "\n")
print(f"scan-to-bench: {scan_cells} scan cells, {len(statements)} gates PASS")
