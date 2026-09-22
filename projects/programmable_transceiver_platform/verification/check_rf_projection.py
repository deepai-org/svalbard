#!/usr/bin/env python3
"""Check the transient measurement independently of circuit simulation."""
import ast
import math
from pathlib import Path

source = Path(__file__).resolve().parents[1] / 'analog/lna_mixer_screen.py'
function = next(node for node in ast.parse(source.read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name == 'projection')
namespace = {'math': math}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
# Deliberately nonuniform samples; neither measurement boundary is a sample.
points = []
for i in range(101001):
    t = (i + .17*math.sin(i*.73))*1e-12
    points.append((t, .23 + .002*math.cos(2*math.pi*100e6*t+.37)
                   + .3*math.sin(2*math.pi*2.3e9*t)))
observed = namespace['projection'](points, 1, 80e-9, 100e-9, 100e6)
expected = .002*complex(math.cos(.37), math.sin(.37))
error = abs(observed-expected)/abs(expected)
assert error < 1e-5, error
print(f'RF projection reference relative error: {error:.3g}')
