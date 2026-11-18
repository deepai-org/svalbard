#!/bin/bash
# LVS proof on the routed fixture (real block cells and placeholders out of the skeleton GDS, nets from pt_chip.conn):
#   positive control must PASS; three negative controls must FAIL:
#   swap    two nets exchanged on one instance in the reference (iso_cdr_up_0 VDD <-> VSS)
#   openvia one routed Via4 removed from the layout
#   bridge  a Metal4 strap drawn across a real block (lands on block-internal metal)
# Needs <run>/skel/pt_chip_skel.gds. Light (seconds). Exit 0 only if all four behave.
. "$(dirname "$0")/../env.sh"
F=${FIXTURE:-aosc,ring_osc,vco_replica,prescale,prescale_conv,prescale_hf,wordclk_rx,obs_pre4_wire,obs_pre4_ref,obs_pre4_pll,iso_cdr_up_0,iso_cdr_dn_0,iso_clk_obs,refvcm,bias_ext,txpad_bias,lo_vreg,isw_pll,lo_obs_q,hsbias}
D=$RUN/lvs/fix; mkdir -p "$D"; rc=0
python3 "$SO/lvs/gen_netlist.py" "$D/fixture.ref.spice" --top pt_fixture --only "$F" || exit 1
python3 "$SO/lvs/gen_netlist.py" "$D/fixture.swap.spice" --top pt_fixture --only "$F" --swap iso_cdr_up_0:VDD:VSS || exit 1
"$SO/kl.sh" lvs/fixture.py -rd insts="$F" || exit 1
"$SO/kl.sh" lvs/fixture.py -rd insts="$F" -rd openvia=1 > /dev/null || exit 1
"$SO/kl.sh" lvs/fixture.py -rd insts="$F" -rd bridge=1 > /dev/null || exit 1
lvs() { "$SO/kl.sh" lvs/top_lvs.py -rd gds=lvs/fix/$1 -rd top=pt_fixture -rd ref=lvs/fix/$2 -rd out=lvs/fix/$3 -rd manifest=lvs/fix/fixture_manifest.json | grep "^LVS"; return ${PIPESTATUS[0]}; }
lvs fixture.gds fixture.ref.spice pos && echo "positive control: PASS (as required)" || { echo "positive control: FAIL"; rc=1; }
lvs fixture.gds fixture.swap.spice neg_swap && { echo "negative control swap: NOT detected"; rc=1; } || echo "negative control swap: detected"
lvs fixture_openvia.gds fixture.ref.spice neg_openvia && { echo "negative control openvia: NOT detected"; rc=1; } || echo "negative control openvia: detected"
lvs fixture_bridge.gds fixture.ref.spice neg_bridge && { echo "negative control bridge: NOT detected"; rc=1; } || echo "negative control bridge: detected"
echo "LVS controls: $([ $rc = 0 ] && echo PASS || echo FAIL)"; exit $rc
