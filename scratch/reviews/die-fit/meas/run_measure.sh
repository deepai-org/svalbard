#!/bin/bash
# one job, one thread, read-only mount of the repo
cd "$(dirname "$0")"
docker run --rm --network none --cpus 1 --memory 8g -e OMP_NUM_THREADS=1 --entrypoint /bin/bash \
  -v /home/ubuntu/svalbard:/repo:ro -v "$PWD":/work -w /work \
  docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3 \
  -lc "nice -n 10 python3 measure.py $* > measure.log 2>&1"; echo "rc=$?" >> measure.log
