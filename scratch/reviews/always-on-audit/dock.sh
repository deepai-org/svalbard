#!/bin/bash
# usage: dock.sh 'command'   (audit helper; project mounted read-only at /proj, this dir at /work)
R=/home/ubuntu/svalbard
A=$R/scratch/reviews/always-on-audit
docker run --rm --platform linux/arm64 --network none --cpus ${CPUS:-6} --memory ${MEM:-12g} --memory-swap ${MEM:-12g} --pids-limit 512 \
 --user "$(id -u):$(id -g)" --env HOME=/tmp --env PDK=gf180mcuD --env PDK_ROOT=/foss/pdks --env PDKPATH=/foss/pdks/gf180mcuD \
 --env OMP_NUM_THREADS=1 \
 --mount type=bind,src=$R/projects/programmable_transceiver_platform,dst=/proj,readonly \
 --mount type=bind,src=$R/scratch/core_support/work/clean,dst=/clean,readonly \
 --mount type=bind,src=$R/scratch/island-support-20261108-075605,dst=/isl,readonly \
 --mount type=bind,src=$R/scratch/core_support/avalon_lib,dst=/foss/pdks/gf180mcuD/libs.ref/gf180mcu_as_sc_mcu7t3v3,readonly \
 --mount type=bind,src=$A,dst=/work --workdir /work --tmpfs /tmp:size=1g,mode=1777 \
 --entrypoint /bin/bash docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3 -lc "$1"
