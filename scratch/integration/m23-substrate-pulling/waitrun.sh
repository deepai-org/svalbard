#!/bin/bash
# waitrun.sh <file-to-wait-for> <dir> <runner> <deck...> : start a sim chain when a result file appears (keeps <= 6 sims running)
f="$1"; shift; d="$1"; shift
until [ -s "$f" ]; do sleep 15; done
sleep 5
cd "$d" && "$@"
