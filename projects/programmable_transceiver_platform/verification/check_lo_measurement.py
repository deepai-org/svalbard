#!/usr/bin/env python3
"""Check edge interpolation and time-weighted averaging on analytic waveforms."""
import ast
from pathlib import Path
source=Path(__file__).resolve().parents[1]/'analog/lo_buffer_screen.py'
nodes=[n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ('crossings','mean')]
ns={}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),ns)
rows=[(0.,0.),(.1,.1),(.8,.8),(1.,1.),(1.2,.8),(1.9,.1),(2.,0.)]
assert ns['crossings'](rows,1,.5,True)==[.5]
assert ns['crossings'](rows,1,.5,False)==[1.5]
assert abs(ns['mean'](rows,1)-.5)<1e-15
assert ns['crossings'](rows,1,1.1,True)==[]
assert ns['crossings']([(0,0),(1,.5),(2,.5),(3,1)],1,.5,True)==[1.]
print('LO measurement checks: nonuniform interpolation, plateau, absent edge, weighted mean passed')
