#!/bin/bash
# run.sh <deck> : ngspice (analog image) single thread
H=/home/ubuntu/svalbard/scratch/integration/signoff-gap/fill/sim
docker run --rm --network none --cpus 1 --memory 8g --user 1000:1000 -e HOME=/tmp -e OMP_NUM_THREADS=1 -v $H:/work -w /work --entrypoint /bin/bash \
  sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 -c "export PATH=\$PATH:/foss/tools/bin:/foss/tools/ngspice/bin; ngspice -b $1 > ${1%.spice}.log 2>&1"
