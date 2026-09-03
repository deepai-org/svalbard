#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path

output = Path(os.environ.get("OUTPUT", "/app/output"))
rtl = output / "rtl"
package = rtl / "lnp64_soc_pkg.sv"
top = rtl / "lnp64_soc.sv"
required = [package, top, output / "integration/soc_manifest.json"]
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise SystemExit("missing required files: " + ", ".join(missing))

sources = [package, *sorted(path for path in rtl.glob("*.sv") if path not in {package, top}), top]
command = ["iverilog", "-g2012", "-s", "tb_lnp64_soc_smoke", "-o", "/tmp/lnp64_visible.vvp"]
command += [str(path) for path in sources]
command += [str(Path(__file__).with_name("tb_lnp64_soc_smoke.sv"))]
subprocess.run(command, check=True)
subprocess.run(["vvp", "/tmp/lnp64_visible.vvp"], check=True)
