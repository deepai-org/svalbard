#!/bin/bash
# run.sh name...  sequential chain = one sim slot
cd "$(dirname "$0")"
for n in "$@"; do
docker run --rm --network none --cpus 2 -e OMP_NUM_THREADS=1 --user $(id -u):$(id -g) -e HOME=/tmp -v $PWD:/work -w /work --entrypoint /bin/bash sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 -lc "ngspice -b $n.spice > $n.log 2>&1"; touch $n.done
done
