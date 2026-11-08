#!/bin/bash
# Runs inside the analog image (hpretl/iic-osic-tools pinned digest): Magic 8.3.678 GDS export,
# then KLayout GF180 DRC on that exported GDS (macro level = all decks except chip-level density
# and antenna; sak-drc.sh -l macro), and the KLayout antenna deck separately.
set -u
export PDK_ROOT=/foss/pdks PDK=gf180mcuD PDKPATH=/foss/pdks/gf180mcuD
export PATH=/foss/tools/bin:/foss/tools/klayout:/foss/tools/sak:$PATH
cd /work
magic --version > magic-version.txt 2>&1
magic -dnull -noconsole -rcfile $PDKPATH/libs.tech/magic/gf180mcuD.magicrc magic_export.tcl > magic-export.log 2>&1
echo "magic_rc=$?"
sha256sum pt_digital_macro.gds > gds.sha256
klayout -v > klayout-version.txt 2>&1
for deck in main antenna; do
  if [ $deck = main ]; then decks="all,-density,-antenna"; else decks="antenna"; fi
  klayout -b -rd input=/work/pt_digital_macro.gds -rd report=/work/klayout-$deck.lyrdb -rd topcell=pt_digital_macro \
    -rd variant=gf180mcuD -rd run_mode=deep -rd threads=3 -rd decks="$decks" \
    -r $PDKPATH/libs.tech/klayout/tech/drc/gf180mcu.drc > klayout-$deck.log 2>&1
  echo "klayout_${deck}_rc=$?"
done
python3 - <<'PY'
import re, json
out = {}
for deck in ('main', 'antenna'):
    try:
        t = open(f'/work/klayout-{deck}.lyrdb').read()
    except OSError:
        out[deck] = None; continue
    cats = {}
    for m in re.finditer(r'<item>.*?<category>(.*?)</category>', t, re.S):
        k = m.group(1).strip("'"); cats[k] = cats.get(k, 0) + 1
    out[deck] = dict(violations=sum(cats.values()), by_rule=cats)
json.dump(out, open('/work/klayout-summary.json', 'w'), indent=1)
print(json.dumps(out))
PY
