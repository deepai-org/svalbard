#!/bin/bash
# sweep.sh <var> <codes> <corner...>   serial chain AC jobs (call through ../../slot.sh; short jobs only)
var=$1; codes=$2; shift 2
for ck in "$@"; do python3 r5lib.py ac $var $ck codes=$codes; done
