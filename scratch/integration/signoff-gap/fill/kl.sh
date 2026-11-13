#!/bin/bash
# kl.sh <script in this dir> [-rd k=v ...]   (paths under /h = this dir, /repo = repository read-only)
H=/home/ubuntu/svalbard/scratch/integration/signoff-gap/fill
S=$1; shift
docker run --rm --network none --cpus 1 --memory 24g --user $(id -u):$(id -g) -e HOME=/tmp -v /home/ubuntu/svalbard:/repo:ro -v $H:/h \
  --entrypoint /bin/bash sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 -c \
  "export PATH=\$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout; klayout -b -r /h/$S $*" 2>&1 | tail -4
