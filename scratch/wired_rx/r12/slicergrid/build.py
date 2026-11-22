"""pt_slicer r7 rebuilt with the chip-grid Metal5 channels kept free (ASM-8, assembly 70 um phase rule); cells unchanged."""
import sys
from pathlib import Path
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'); sys.path.insert(0, str(W))
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/timing/asm10')
import slicer_compact as s, gridkeep
H = Path(__file__).resolve().parent
s.SCRATCH = H / 'work'
s.build_top(em=dict(m5_keep=gridkeep.keep(float(sys.argv[1]) if len(sys.argv) > 1 else 1.5)), gen=H / 'gen')
