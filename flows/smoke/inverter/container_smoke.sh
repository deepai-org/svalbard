#!/usr/bin/env bash
set -euo pipefail

xschem -s -r -x -q \
  --rcfile "$PDK_ROOT/$PDK/libs.tech/xschem/xschemrc" \
  --command 'set spiceprefix 1; set lvs_netlist 0; set top_is_subckt 1; set lvs_ignore 1; set ev_precision 5; set netlist_dir /work; xschem set netlist_name inverter_magic.spice; xschem netlist' \
  /src/inverter.sch > /work/xschem.log 2>&1
test -s /work/inverter_magic.spice

ngspice -b -o /work/prelayout.log /src/prelayout_tb.spice > /work/ngspice-pre.stdout 2>&1

magic -dnull -noconsole \
  -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/layout.log 2>&1
test -s /work/inverter.mag

sak-drc.sh -m -w /work/drc /work/inverter.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs \
  -s /work/inverter_magic.spice \
  -l /work/inverter.mag \
  -c inverter > /work/lvs-stage.log 2>&1
sak-pex.sh -m 2 -n inverter_pex -w /work/pex \
  /work/inverter.mag > /work/pex-stage.log 2>&1
test -s /work/pex/inverter.pex.spice

ngspice -b -o /work/postlayout.log /src/postlayout_tb.spice > /work/ngspice-post.stdout 2>&1

python3 /src/check_results.py \
  --golden /src/golden.json \
  --prelayout /work/prelayout.log \
  --postlayout /work/postlayout.log \
  --drc /work/drc/inverter.magic.drc/inverter.magic.drc.rpt \
  --lvs /work/lvs/inverter.magic.lvs/inverter.lvs.out \
  --output /work/result.json
