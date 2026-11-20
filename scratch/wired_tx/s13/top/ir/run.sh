#!/bin/sh
# IR / EM of the block supplies from the drawn geometry (s13/top/REPORT.md section 6).  One docker job (KLayout raster), then local.
#   sh run.sh [gds]     default: ../out/pt_wiredtx8.gds ; geometry / tie points from ../out/report.json
set -e
cd "$(dirname "$0")"
G=${1:-../out/pt_wiredtx8.gds}
mkdir -p r && cp "$G" r/b.gds && cp ras.py r/
docker run --rm --network none --cpus 1 --memory 8g -e OMP_NUM_THREADS=1 -v "$PWD/r":/work -w /work --entrypoint /bin/bash \
  docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3 -lc 'python3 ras.py b.gds 0.5' > r/ras.log 2>&1
BANDS='[{"net": "VSS", "name": "VSS rail + plate (seam)", "axis": "x", "lo": 214.84, "hi": 229.44, "from": 1, "to": 743}, {"net": "VDD", "name": "VDD rail (seam)", "axis": "x", "lo": 230.34, "hi": 235.44, "from": 1, "to": 743}, {"net": "VSS", "name": "VSS bars + corner stubs (y cuts)", "axis": "y", "lo": 575, "hi": 744, "from": 229.86, "to": 236.36}, {"net": "VSS", "name": "mux VSS necks (y cut)", "axis": "y", "lo": 242, "hi": 567, "from": 230.46, "to": 236.36}, {"net": "VDD", "name": "VDD ties T_main -> header (x cut)", "axis": "x", "lo": 393.64, "hi": 401.34, "from": 313.1, "to": 360.75}, {"net": "VDD", "name": "VDD ties T_post -> header (x cut)", "axis": "x", "lo": 393.64, "hi": 401.34, "from": 455.65, "to": 503.9}, {"net": "VSS", "name": "VSS trunk x 335-345 (y cuts)", "axis": "y", "lo": 334.5, "hi": 345.5, "from": 1, "to": 213.86}, {"net": "VSS", "name": "VSS trunk x 366.5-376.5 (y cuts)", "axis": "y", "lo": 366.0, "hi": 377.0, "from": 1, "to": 213.86}, {"net": "VSS", "name": "VSS trunk x 475-485 (y cuts)", "axis": "y", "lo": 474.5, "hi": 485.5, "from": 1, "to": 213.86}]'
for ph in O; do export PHASE=$ph TIEW=${TIEW:-10.5};   # assembly: phase O, 10.5 um grid straps (WT47)
 T=$(python3 ties.py ../out/report.json); for c in nom high; do
  python3 mkcfg.py r "$T" r/$c.json 1.0 $c && python3 -c "import json,sys; c=json.load(open(sys.argv[1])); c['map']='r/'+sys.argv[2]; json.dump(c,open(sys.argv[1],'w'))" r/$c.json $c
  OMP_NUM_THREADS=1 python3 ir.py r/$c.json > ir_$c.json
  python3 emlines.py r/$c.json r/$c "$BANDS" > em_$c.json
done; mkdir -p ph$ph; mv ir_*.json em_*.json ph$ph/; done
rm -rf r
