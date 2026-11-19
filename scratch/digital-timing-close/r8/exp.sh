#!/bin/bash
# exp.sh <run-out-dir (mounted /out)> <TAG> <env step dir> <odb step dir> <variant> [extra docker -e ...]
R=$1; TAG=$2; ES=$3; OS=$4; V=$5; shift 5
mkdir -p $R/exp
docker run --rm --network none --cpus 2 --memory 12g --user "$(id -u):$(id -g)" -e HOME=/out/home -e TMPDIR=/out/tmp -e OMP_NUM_THREADS=1 \
 -e EXP_ENV=/out/design/runs/$TAG/$ES/_env.tcl -e EXP_ODB=/out/design/runs/$TAG/$OS/pt_digital_macro.odb -e EXP_VAR=$V -e EXP_OUT=/out/exp "$@" \
 -v /home/ubuntu/svalbard/projects/programmable_transceiver_platform:/src:ro -v $R:/out -v /home/ubuntu/svalbard/scratch/digital-timing-close/r8:/r8:ro \
 --entrypoint /bin/bash svalbard/librelane-gf180-guarded:2026.11 -lc "cd /out/exp && openroad -exit -no_splash -threads 2 /r8/exp.tcl" > $R/exp/$V.log 2>&1
echo "$V rc=$?" >> $R/exp/status
