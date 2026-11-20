"""Build the ct_locml macro with `units` per side/2 into var/<v>/generated/fast (staging; shared generated/ untouched).
usage: mkml.py <variant> <units>"""
import sys
from pathlib import Path
T = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'
sys.path.insert(0, T)
import timing_flow as tf
import fastcells as fc
v, u = sys.argv[1], int(sys.argv[2])
H = Path(__file__).resolve().parent
tf.GENERATED = H / 'var' / v / 'generated'
tf.SCRATCH = H / 'var' / v / 'build'
fc.CELLS['ct_locml'] = lambda: fc.locml(units=u)
fc.build('ct_locml')
