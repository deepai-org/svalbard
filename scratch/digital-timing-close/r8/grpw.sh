#!/bin/bash
# grpw.sh <report_checks file> [limit]: worst slack per path group (startpoint -> endpoint)
awk '/^Startpoint/{sp=$2} /^Endpoint/{ep=$2} /^Path Group/{g=$3} /slack \(/{print g, $1, sp, ep}' $1 | sed 's/_gf180mcu_fd_sc_mcu7t5v0__[A-Za-z0-9_]*//g' \
 | awk '{if(!($1 in s)){s[$1]=$2; l[$1]=$3" -> "$4}} END{for(g in s) printf "%8.2f %-14s %s\n", s[g], g, l[g]}' | sort -n | awk -v m=${2:-1.0} '$1<m' | cut -c1-150
