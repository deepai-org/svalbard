# detail.sh <rundir> <tag> ; env LIBPVT RC TC RATE K CLKS NP SDCDIR
SDCDIR=${SDCDIR:-/home/ubuntu/svalbard-macro/projects/programmable_transceiver_platform/integration}
docker run --rm --name dig-mb-sta-$2 --network none --cpus 1 --memory 8g --user $(id -u):$(id -g) -e HOME=/tmp -e OMP_NUM_THREADS=1 \
 -e LIBPVT="$LIBPVT" -e RC="$RC" -e TC="$TC" -e RATE="$RATE" -e K="$K" -e CLKS="$CLKS" -e NP="${NP:-3}" \
 -v /home/ubuntu/svalbard-macro/projects/programmable_transceiver_platform/verification/digital_hardening/liberty:/clib:ro -v $SDCDIR:/sdc:ro \
 -v $1:/mrun:ro -v /home/ubuntu/svalbard-macro/scratch/digital-macro-batch/sta:/w:ro --entrypoint /bin/bash svalbard/librelane-gf180-guarded:2026.11 -lc 'sta -no_init -exit /w/detail.tcl' > /home/ubuntu/svalbard-macro/scratch/digital-macro-batch/sta/$2.log 2>&1
