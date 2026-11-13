#!/usr/bin/env bash
# run.sh <name>...   run decks runs/<name>.sp in the pinned analog image, max $PAR (default 6) at a time, 1 CPU each
IMG=docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3
HERE=$(cd "$(dirname "$0")" && pwd)
printf '%s\n' "$@" | xargs -P "${PAR:-6}" -I{} docker run --rm --network none --cpus 1 --memory 6g --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -e OMP_NUM_THREADS=1 -v /home/ubuntu/svalbard:/home/ubuntu/svalbard:ro -v "$HERE/runs":"$HERE/runs" -w "$HERE/runs" \
  --entrypoint /bin/bash "$IMG" -lc 'ngspice -b {}.sp > {}.log 2>&1; echo "{} rc=$?" >> done.txt'
