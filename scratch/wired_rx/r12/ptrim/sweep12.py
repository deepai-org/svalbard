"""r10ptrim/sweep.py (32-code ideal-source sweep, criteria C1..C5) run with its work dir and store in this directory."""
import sys, runpy
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/wired_rx/r10ptrim')
import bench, savefix, sweep
bench.H = H; sweep.H = H
sys.argv[0] = 'sweep.py'; sweep.main()
