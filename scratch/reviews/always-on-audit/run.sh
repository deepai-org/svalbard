#!/bin/bash
# usage: run.sh <group> [glob] [jobs] [timeout_s]   -- runs /work/<group>/<glob>.sp in the pinned analog image
g=$1; pat=${2:-*}; jobs=${3:-6}; to=${4:-1500}
here="$(cd "$(dirname "$0")" && pwd)"
CPUS=$jobs "$here/dock.sh" "cd /work/$g && printf 'set ngbehavior=hsa\nset ng_nomodcheck\nset num_threads=1\n' > /tmp/.spiceinit && ls $pat.sp | sed 's/\.sp\$//' | xargs -P $jobs -I{} sh -c 'timeout $to ngspice -b {}.sp > {}.log 2>&1; echo {} rc=\$?'" 2>&1 | grep -v '^\[INFO\]'
