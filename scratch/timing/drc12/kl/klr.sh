#!/bin/bash
# run a klayout python script in the project image: klr.sh script.py [-rd k=v]; /repo ro, /w = this dir's parent rw
D=$(cd "$(dirname "$0")/.." && pwd); S=$1; shift
exec docker run --rm --network none --cpus 2 --memory 16g --user "$(id -u):$(id -g)" -e HOME=/tmp -e OMP_NUM_THREADS=1 \
 -v /home/ubuntu/svalbard:/repo:ro -v "$D":/w --entrypoint /bin/bash sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 -c \
 'export PATH=$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout; cd /w; exec klayout -b -zz -r "$@"' kl "$S" "$@"
