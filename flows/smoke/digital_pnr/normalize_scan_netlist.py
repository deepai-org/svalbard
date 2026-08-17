#!/usr/bin/env python3
import re
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: normalize_scan_netlist.py INPUT OUTPUT")

source, output = map(Path, sys.argv[1:])
text = source.read_text()

for cell, expected in (("endcap", 32), ("filltie", 27)):
    pattern = rf"\n gf180mcu_fd_sc_mcu7t5v0__{cell} [^\n]+ \(\);"
    text, count = re.subn(pattern, "", text)
    if count != expected:
        raise SystemExit(f"expected {expected} {cell} cells, found {count}")

pattern = r" assign scan_out_0 = ([A-Za-z0-9_]+);"
match = re.search(pattern, text)
if match is None or len(re.findall(pattern, text)) != 1:
    raise SystemExit("expected one scan output alias")
net = match.group(1)
buffer = (
    " gf180mcu_fd_sc_mcu7t5v0__buf_1 scan_output "
    f"(.I({net}),\n    .Z(scan_out_0));"
)
text = re.sub(pattern, buffer, text)
if " assign " in text:
    raise SystemExit("assignment remains in normalized netlist")
output.write_text(text)
