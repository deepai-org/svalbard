# sta.sh <chip rf|wired> <tag> ; env LIBPVT RC TC RATE K DLY
R=/home/ubuntu/svalbard/scratch/digital_hardening-$1-m5/design/runs/RF; [ $1 = wired ] && R=/home/ubuntu/svalbard/scratch/digital_hardening-wired-d80/design/runs/WIRED
docker run --rm --name dig-$1-pdn02-$2 --network none --cpus 1 --memory 8g --user $(id -u):$(id -g) -e HOME=/tmp -e OMP_NUM_THREADS=1 -e PT_CHIP=$1 \
 -e LIBPVT=$LIBPVT -e RC=$RC -e TC=$TC -e RATE=$RATE -e K=$K -e DLY=$DLY \
 -v /home/ubuntu/svalbard/projects/programmable_transceiver_platform/verification/digital_hardening/liberty:/clib:ro -v /home/ubuntu/svalbard/projects/programmable_transceiver_platform/integration:/sdc:ro \
 -v $R:/mrun:ro -v /home/ubuntu/svalbard/scratch/pdn02-boot:/w:ro --entrypoint /bin/bash svalbard/librelane-gf180-guarded:2026.11 -lc 'sta -no_init -exit /w/sta_b.tcl' > /home/ubuntu/svalbard/scratch/pdn02-boot/out/b-$1-$2.log 2>&1
