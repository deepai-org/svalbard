#!/bin/bash
# grp.sh <step-dir>: worst setup (max.rpt) and hold (min.rpt) slack per path group of a LibreLane STA step
for k in max min; do
  echo "== $k $(basename $1)"
  awk '/^Startpoint/{sp=$2} /^Endpoint/{ep=$2} /^Path Group/{g=$3} /slack \(/{print g, $1, sp, ep}' $1/$k.rpt | sed 's/_gf180mcu_fd_sc_mcu7t5v0__[A-Za-z0-9_]*//g' \
   | awk '{if(!($1 in s)){s[$1]=$2; l[$1]=$3" -> "$4}} END{for(g in s) printf "%8.2f %-14s %s\n", s[g], g, l[g]}' | sort -n | awk -v k=$k '$1 < (k=="max" ? 1.0 : 0.3)' | cut -c1-150
done
