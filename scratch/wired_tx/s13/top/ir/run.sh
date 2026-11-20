#!/bin/sh
# IR / EM of the block supplies from the drawn geometry (s13/top/REPORT.md section 6).  One docker job (KLayout raster), then local.
#   sh run.sh [gds]     default: ../out/pt_wiredtx8.gds ; geometry / tie points from ../out/report.json
set -e
cd "$(dirname "$0")"
G=${1:-../out/pt_wiredtx8.gds}
mkdir -p r && cp "$G" r/b.gds && cp ras.py r/
docker run --rm --network none --cpus 1 --memory 8g -e OMP_NUM_THREADS=1 -v "$PWD/r":/work -w /work --entrypoint /bin/bash \
  docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3 -lc 'python3 ras.py b.gds 0.5' > r/ras.log 2>&1
BANDS='[{"net":"VSS","name":"VSS rail + plate (seam)","axis":"x","lo":214.0,"hi":228.6,"from":1,"to":743},{"net":"VDD","name":"VDD rail (seam)","axis":"x","lo":229.5,"hi":234.6,"from":1,"to":743},{"net":"VSS","name":"VSS bars + corner stubs (y cuts)","axis":"y","lo":575,"hi":744,"from":229,"to":235.5},{"net":"VSS","name":"mux VSS necks (y cut)","axis":"y","lo":242,"hi":567,"from":229.6,"to":235.5},{"net":"VDD","name":"VDD tie T_main -> header (x cut)","axis":"x","lo":392.8,"hi":400.5,"from":352,"to":381},{"net":"VDD","name":"VDD tie T_post -> header (x cut)","axis":"x","lo":392.8,"hi":400.5,"from":478,"to":504},{"net":"VSS","name":"VSS trunk x 335-345 (y cuts)","axis":"y","lo":334.5,"hi":345.5,"from":1,"to":213},{"net":"VSS","name":"VSS trunk x 405-415 (y cuts)","axis":"y","lo":404.5,"hi":415.5,"from":1,"to":213},{"net":"VSS","name":"VSS trunk x 475-485 (y cuts)","axis":"y","lo":474.5,"hi":485.5,"from":1,"to":213}]'
for ph in A B; do export PHASE=$ph; T=$(python3 ties.py ../out/report.json); for c in nom high; do
  python3 mkcfg.py r "$T" r/$c.json 1.0 $c && python3 -c "import json,sys; c=json.load(open(sys.argv[1])); c['map']='r/'+sys.argv[2]; json.dump(c,open(sys.argv[1],'w'))" r/$c.json $c
  OMP_NUM_THREADS=1 python3 ir.py r/$c.json > ir_$c.json
  python3 emlines.py r/$c.json r/$c "$BANDS" > em_$c.json
done; mkdir -p ph$ph; mv ir_*.json em_*.json ph$ph/; done
rm -rf r
