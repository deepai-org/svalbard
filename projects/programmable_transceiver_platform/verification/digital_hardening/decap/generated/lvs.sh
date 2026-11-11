export PDK_ROOT=/foss/pdks PDK=gf180mcuD PDKPATH=/foss/pdks/gf180mcuD
export PATH=/foss/tools/bin:/foss/tools/klayout:$PATH
cd /w
python3 - <<'PY'
# one reference netlist per top cell
t=open('/w/pt_decap50.spice').read().split('.subckt ')
for blk in t[1:]:
    name=blk.split()[0]
    open(f'/w/{name}.cdl','w').write('.subckt '+blk)
PY
for c in pt_decap50_4 pt_decap50_8 pt_decap50_16 pt_decap50_32 pt_decap50_64; do
  python3 $PDKPATH/libs.tech/klayout/tech/lvs/run_lvs.py --layout=/w/pt_decap50.gds --netlist=/w/$c.cdl --variant=D --topcell=$c --run_dir=/w/lvs_$c --run_mode=flat --top_lvl_pins > /w/lvs_$c.log 2>&1
  echo "$c rc=$?"; grep -E "Netlists" /w/lvs_$c.log | tail -1
done
