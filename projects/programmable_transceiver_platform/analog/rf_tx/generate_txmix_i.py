"""Layout generator entry point for txmix_i (see generate.py / layoutlib.py)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate  # noqa: E402

if __name__ == '__main__':
    r = generate.generate('txmix_i', generate.REPO / 'scratch/rf_tx/layout', generate.HERE / 'generated')
    print(json.dumps({k: r[k] for k in ('block', 'drc_errors', 'lvs_unique_match', 'area_um2', 'area_ceiling_um2')}))
