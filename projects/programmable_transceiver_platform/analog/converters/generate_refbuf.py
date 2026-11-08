#!/usr/bin/env python3
"""Reproducible layout generator for refbuf: schematic, Magic layout, DRC, LVS,
extracted simulations and evidence (see flow.py; runs in the pinned images)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow  # noqa: E402

if __name__ == '__main__':
    flow.run_block('refbuf', corners=(sys.argv[sys.argv.index('--corners') + 1] if '--corners' in sys.argv else 'all'))
