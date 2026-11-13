#!/bin/bash
# PDK fill (libs.tech/klayout/tech/scripts/fill_all.rb, PDK f6eeac7, KLayout 0.30.9) on a COPY.
#   run_fill.sh <input gds (abs)> <output name in ./out> <threads> [extra -rd args, e.g. "-rd Metal1_ignore_active=true"]
set -e
H=/home/ubuntu/svalbard/scratch/integration/signoff-gap/fill
mkdir -p $H/out
IN=$(realpath "$1")
docker run --rm --network none --cpus $3 --memory 24g --user $(id -u):$(id -g) -e HOME=/tmp \
  -v "$IN":/in/in.gds:ro -v $H/out:/out -v $H/fill_wrap.rb:/s/fill_wrap.rb:ro --entrypoint /bin/bash \
  sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 -c \
  "export PATH=\$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout; cd /tmp; /usr/bin/time -v klayout -b -r /s/fill_wrap.rb -rd input=/in/in.gds -rd output=/out/$2 -rd thr=$3 $4" > $H/out/$2.log 2>&1
echo EXIT $? >> $H/out/$2.log
