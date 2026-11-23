#!/bin/bash
# usage: build.sh <family> <name> '<site opt JSON>'   -> b/<name>.gds (+ .json). ONE job.
cd /home/ubuntu/svalbard/scratch/pads-core/esdopt/rf
I=sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43
docker run --rm --network none -e OMP_NUM_THREADS=1 --user $(id -u):$(id -g) --entrypoint python3 -v /home/ubuntu/svalbard:/home/ubuntu/svalbard -w $PWD $I \
  rf_compose.py $1 ../pins/b/pad_$1.gds b/$2.gds "$3"
