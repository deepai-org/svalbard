set -u
export PDK_ROOT=/foss/pdks PDK=gf180mcuD PDKPATH=/foss/pdks/gf180mcuD
export PATH=/foss/tools/bin:/foss/tools/klayout:$PATH
cd /w
for top in pt_decap50_test pt_decap50_64; do
for deck in main antenna; do
  if [ $deck = main ]; then decks="all,-density,-antenna"; else decks="antenna"; fi
  klayout -b -rd input=/w/$( [ $top = pt_decap50_test ] && echo pt_decap50_test.gds || echo pt_decap50.gds ) -rd report=/w/drc-$top-$deck.lyrdb -rd topcell=$top \
    -rd variant=gf180mcuD -rd run_mode=deep -rd threads=4 -rd decks="$decks" \
    -r $PDKPATH/libs.tech/klayout/tech/drc/gf180mcu.drc > /w/drc-$top-$deck.log 2>&1
  echo "$top $deck rc=$?"
done; done
python3 - <<'PY'
import re
for f in ['drc-pt_decap50_test-main','drc-pt_decap50_test-antenna','drc-pt_decap50_64-main','drc-pt_decap50_64-antenna']:
    t=open(f'/w/{f}.lyrdb').read()
    cats={}
    for m in re.finditer(r'<item>.*?<category>(.*?)</category>', t, re.S):
        k=m.group(1).strip("'"); cats[k]=cats.get(k,0)+1
    print(f, sum(cats.values()), cats)
PY
