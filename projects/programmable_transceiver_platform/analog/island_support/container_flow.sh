#!/usr/bin/env bash
# Container-side flow (pinned iic-osic-tools image): schematic campaign,
# layout + DRC + LVS + PEX for every cell, extracted campaign.
set -euo pipefail
SRC=/src/analog/island_support
N="${WORKERS:-$(nproc)}"
python3 "$SRC/sim.py" --workers "$N" --out /work/schematic-result.json > /work/schematic.log 2>&1
cells=$(python3 - <<'PY'
import json
s = json.load(open('/work/schematic-result.json'))
out = [f"isw_{i}:isw:{v['fingers']}" for i, v in s['sizes'].items()]
out += ['atb_leaf_s:atb:-', 'atb_leaf_f:atb:-', 'atb_grp:atb:-', 'atb_pad:atb:-', 'iso_clamp:logic:-']
print(' '.join(out))
PY
)
bash "$SRC/physical.sh" $cells > /work/physical.log 2>&1
python3 "$SRC/extracted.py" --workers "$N" --out /work/extracted-result.json > /work/extracted.log 2>&1
python3 "$SRC/rc_check.py" > /work/rc.log 2>&1
python3 "$SRC/integration.py" > /work/integration.log 2>&1
echo "container flow done"
