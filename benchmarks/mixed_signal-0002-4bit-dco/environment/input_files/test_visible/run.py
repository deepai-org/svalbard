#!/usr/bin/env python3
from pathlib import Path
import json, os, re, shutil, subprocess, sys, tempfile

candidate = Path(sys.argv[1] if len(sys.argv)>1 else "/app/output").resolve()
spice = candidate / "analog/dco4.spice"
manifest = candidate / "integration/dco4.json"
expected = {"top":"dco4","pins":["EN","CTRL0","CTRL1","CTRL2","CTRL3","OUT","VDD","VSS"],"supply_v":3.3}
if json.loads(manifest.read_text()) != expected:
    raise SystemExit("manifest mismatch")
text = spice.read_text()
if not re.search(r"(?im)^\.subckt\s+dco4\s+EN\s+CTRL0\s+CTRL1\s+CTRL2\s+CTRL3\s+OUT\s+VDD\s+VSS\s*$", text):
    raise SystemExit("SPICE top signature mismatch")
pdk = Path(os.environ.get("PDK_ROOT","/foss/pdks")) / "gf180mcuD"
models = pdk / "libs.tech/ngspice/sm141064.ngspice"
cells = pdk / "libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice"
if not models.is_file() or not cells.is_file():
    print("VISIBLE_PASS interface-only (GF180 models unavailable)")
    raise SystemExit(0)
with tempfile.TemporaryDirectory() as td:
    td=Path(td); deck=td/"test.spice"; log=td/"ngspice.log"
    code=int(os.environ.get("DCO_CODE","0"),0)
    controls=[3.3 if code & (1<<bit) else 0.0 for bit in range(4)]
    deck.write_text(f'''public DCO code-0 smoke
.param fnoicor=1 sw_stat_mismatch=0
.lib {models} typical
.include {cells}
.include {spice}
VVDD vdd 0 3.3
VEN en 0 PWL(0 0 20n 0 21n 3.3)
VC0 c0 0 {controls[0]}
VC1 c1 0 {controls[1]}
VC2 c2 0 {controls[2]}
VC3 c3 0 {controls[3]}
XU en c0 c1 c2 c3 out vdd 0 dco4
CLOAD out 0 20f
.option method=gear reltol=1e-3
.tran 2n 1.5u uic
.measure tran t1 WHEN v(out)=1.65 RISE=3
.measure tran t2 WHEN v(out)=1.65 RISE=8
.measure tran vmax MAX v(out) FROM=0.5u TO=1.5u
.measure tran vmin MIN v(out) FROM=0.5u TO=1.5u
.end
''')
    ngspice=shutil.which("ngspice") or "/foss/tools/bin/ngspice"
    result=subprocess.run([ngspice,"-b","-o",log,deck],cwd=td)
    output=log.read_text(errors="replace")
    if result.returncode or "Error:" in output:
        print(output); raise SystemExit("ngspice failed")
    vals={k:float(v) for k,v in re.findall(r"(?m)^(t1|t2|vmax|vmin)\s*=\s*([-+0-9.eE]+)",output)}
    if set(vals)!={"t1","t2","vmax","vmin"} or vals["t2"]<=vals["t1"]:
        print(output); raise SystemExit("oscillation measurement failed")
    freq=5.0/(vals["t2"]-vals["t1"])
    if not 5e6 <= freq <= 110e6 or vals["vmax"]<2.97 or vals["vmin"]>0.33:
        raise SystemExit(f"code-{code} limits failed: {freq/1e6:.3f} MHz")
    print(f"VISIBLE_PASS code{code}={freq/1e6:.3f}MHz")
