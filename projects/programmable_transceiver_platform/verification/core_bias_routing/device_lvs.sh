#!/bin/bash
# Device-level LVS of the routed core-bias assembly (Magic flat extraction of
# the complete routed GDS, masters included, against the schematic reference
# from device_lvs_reference.py). Expects in /work:
#   pt_core_bias_routed.gds  routed GDS (copied from the routing run)
#   reference.spice          non-circular reference (schematic leaves)
#   reference_neg.spice      same reference with one swapped instance net
#   reference_neg_swap.spice two consumers' bank outputs exchanged
#   routed.json              routing-run geometry (for the layout negative)
# and the Avalon standard-cell library mounted at its PDK path.
set -u
cd /work
AVALON=/foss/pdks/gf180mcuD/libs.ref/gf180mcu_as_sc_mcu7t3v3/spice/gf180mcu_as_sc_mcu7t3v3.spice
SETUP=/foss/pdks/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl
test -s "$AVALON" || { echo "missing Avalon spice"; exit 1; }
mkdir -p ext
cat > extract.tcl <<'EOF'
crashbackups stop
drc off
gds readonly true
gds read /work/pt_core_bias_routed.gds
load pt_core_bias
flatten pt_core_bias_flat
load pt_core_bias_flat
select top cell
extract path /work/ext
extract no all
extract all
feedback save /work/extract_feedback.txt
ext2spice lvs
ext2spice -p /work/ext -o /work/layout_flat.spice
quit -noprompt
EOF
magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc extract.tcl > extract.log 2>&1
test -s layout_flat.spice || { tail -40 extract.log; exit 1; }
# Layout negative control: the routing flow's VDD-VSS Metal3 bridge, applied
# to the complete routed GDS (devices included). LVS must reject it.
klayout -b -r /flow/device_lvs_negative.py > negative_layout.log 2>&1 || { cat negative_layout.log; exit 1; }
mkdir -p neg/ext
sed -e 's#/work/pt_core_bias_routed.gds#/work/neg/pt_core_bias_routed.gds#' -e 's#/work/ext#/work/neg/ext#g' \
    -e 's#/work/layout_flat.spice#/work/neg/layout_flat.spice#' -e 's#/work/extract_feedback.txt#/work/neg/extract_feedback.txt#' extract.tcl > neg/extract.tcl
magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc neg/extract.tcl > neg/extract.log 2>&1
sed 's/pnp_10p00x00p42/pnp_05p00x05p00/g' neg/layout_flat.spice > neg/layout_flat_pnpalias.spice
# Magic recognition alias (identical to the qualified core-support bandgap
# LVS): the bandgap's 10x10 PNP array cells are reported as pnp_10p00x00p42.
grep -c 'pnp_10p00x00p42' layout_flat.spice > pnp_alias_count.txt || true
sed 's/pnp_10p00x00p42/pnp_05p00x05p00/g' layout_flat.spice > layout_flat_pnpalias.spice
run_lvs() {  # $1 reference, $2 report, [$3 layout netlist]
  cat > "$2.tcl" <<EOF
set circuit1 [readnet spice ${3:-/work/layout_flat_pnpalias.spice}]
set circuit2 [readnet spice $AVALON]
readnet spice /work/$1 \$circuit2
lvs "\$circuit1 pt_core_bias_flat" "\$circuit2 pt_core_bias" $SETUP /work/$2
EOF
  NETGEN_COLUMNS=100 netgen -batch source "$2.tcl" > "$2.log" 2>&1 < /dev/null
}
run_lvs reference.spice lvs_device.out
run_lvs reference_neg.spice lvs_device_neg.out
run_lvs reference_neg_swap.spice lvs_device_neg_swap.out
run_lvs reference.spice lvs_device_neg_layout.out /work/neg/layout_flat_pnpalias.spice
echo done
