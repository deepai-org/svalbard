"""mkvar.py <var> NAME=value ...  : schematic what-if variant of netlists.ctle() with module constants overridden -> v/<var>/ctle.ext.spice"""
import sys, ast
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx')
import netlists as n
var = sys.argv[1]
for a in sys.argv[2:]:
    k, v = a.split('=', 1); setattr(n, k, ast.literal_eval(v))
d = Path(__file__).resolve().parent / 'v' / var; d.mkdir(parents=True, exist_ok=True)
(d / 'ctle.ext.spice').write_text(n.ctle().emit()); print(d)
