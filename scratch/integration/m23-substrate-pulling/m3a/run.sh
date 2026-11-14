#!/bin/bash
# run.sh name   (one deck, inside the PDK image, 2 cpus)
cd "$(dirname "$0")"
docker run --rm --network none --cpus 2 -e OMP_NUM_THREADS=1 --user $(id -u):$(id -g) -e HOME=/tmp -v $PWD:/w --entrypoint /bin/bash sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 -lc "cd /w && ngspice -b $1.cir > $1.log 2>&1"
