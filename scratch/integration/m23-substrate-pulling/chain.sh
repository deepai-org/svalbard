#!/bin/bash
# chain.sh <file-to-wait-for> <item>...   item = a:<deck> (m3a ring pair) or q:<deck> (QVCO); runs them one after another = ONE sim slot
W="$(cd "$(dirname "$0")" && pwd)"; f="$1"; shift
until [ -s "$f" ]; do sleep 15; done; sleep 5
for it in "$@"; do
  case "$it" in a:*) "$W/m3a/run.sh" "${it#a:}";; q:*) "$W/m3/qvco/run2.sh" "${it#q:}";; esac
done
