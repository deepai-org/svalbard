#!/bin/bash
# run_dens.sh <gds abs> <out json name in ./out> [tile um]
H=/home/ubuntu/svalbard/scratch/integration/signoff-gap/fill
docker run --rm --network none --cpus 1 --memory 24g --user $(id -u):$(id -g) -e HOME=/tmp -v "$(realpath $1)":/in/in.gds:ro -v $H:/h \
  --entrypoint /bin/bash sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 -c \
  "export PATH=\$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout; klayout -b -r /h/dens.py -rd gds=/in/in.gds -rd out=/h/out/$2 -rd tile=${3:-0}" 2>&1 | tail -3
