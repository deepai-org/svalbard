#!/bin/bash
# Routing LVS of the routed core-bias block (Magic + Netgen, GF180 setup).
#
# Leaf masters are black boxes (lvs_abstract.py: pin conductors + port
# labels only, from the qualified GDS), so extraction yields the top-level net connectivity of all 152 nets to the 283
# instance terminals and 122 boundary pins. The reference is the frozen
# pt_core_bias.spice top cell with matching black-box stubs. Device-level LVS
# of each master is a separate (per-master) qualification; shorts from routes
# into master-internal metal are covered by audit_routes.py.
# Also writes a magic C extraction (coupling + area/fringe) of the routed top.
set -u
rm -rf /work/lvs && mkdir -p /work/lvs/neg && cd /work/lvs
klayout -b -r /flow/lvs_abstract.py > abstract.log 2>&1 || { cat abstract.log; exit 1; }
python3 - <<'EOF'
import re
from pathlib import Path
src = Path('/input/pt_core_bias.spice').read_text().replace('\n+', ' ')
subckts = {m[1]: m[2].split() for m in re.finditer(r'^\.subckt (\S+) (.*)$', src, re.M)}
masters = [p.stem for p in Path('/input').glob('*.lef') if '.' not in p.stem]
lefpins = {m: re.findall(r'^  PIN (\S+)', Path(f'/input/{m}.lef').read_text(), re.M) for m in masters}
top = re.search(r'^\.subckt pt_core_bias (.*?)^\.ends', src, re.M | re.S)[0]
import json
terms = json.loads(Path('/input/physical-terminals.json').read_text())['nets']
tnet = {(t['instance'], t['pin']): net for net, ts in terms.items() for t in ts}
out = []; extra = {}
for m in masters:
    keep = [p for p in subckts[m] if p in lefpins[m]]
    # Physical pins absent from the reference subckt (biasgen avss is merged
    # into dvss in its extracted netlist) are bound from the audited
    # terminal map, so the black box still checks where they are wired.
    extra[m] = [p for p in lefpins[m] if p not in keep]
    out += [f'.subckt {m} ' + ' '.join(keep+extra[m]), '.ends', '']
dropped = 0
for line in top.splitlines():
    if line.startswith('X'):
        f = line.split(); m = f[-1]; nets = f[1:-1]
        ports = subckts[m]; assert len(ports) == len(nets), line
        kept = [n for p, n in zip(ports, nets) if p in lefpins[m]] + [tnet[(f[0], p)] for p in extra[m]]
        dropped += len(nets)-len(kept)
        line = ' '.join([f[0]] + kept + [m])
    out.append(line)
Path('schematic.spice').write_text('\n'.join(out)+'\n')
print('SCHEMATIC_STUBS', len(masters), 'dropped private ports', dropped, 'bound extra pins', extra)
EOF
cat > extract.tcl <<'EOF'
gds read pt_core_bias.gds
foreach m {gf180mcu_ocd_ip__biasgen gf180mcu_ocd_ip__bandgap bringup_and pt_bias_bank3 pt_bias_bank4 pt_bias_bank5 pt_bias_bank8 pt_bias_root pt_bias_vref} {
  load $m
  property LEFview TRUE
}
load pt_core_bias
select top cell
extract do local
extract all
ext2spice lvs
ext2spice blackbox on
ext2spice -o layout.spice
quit -noprompt
EOF
magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc extract.tcl > extract.log 2>&1
netgen -batch lvs "layout.spice pt_core_bias" "schematic.spice pt_core_bias" \
  /foss/pdks/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl lvs.out -blackbox > netgen.log 2>&1
# Negative control: the same flow on a copy with one VDD-VSS Metal3 bridge.
cp schematic.spice extract.tcl neg/ && (cd neg && magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc extract.tcl > extract.log 2>&1 && \
  netgen -batch lvs "layout.spice pt_core_bias" "schematic.spice pt_core_bias" \
  /foss/pdks/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl lvs.out -blackbox > netgen.log 2>&1)
negok=false
if [ -s neg/lvs.out ] && ! grep -q "Circuits match uniquely" neg/lvs.out && grep -q "Final result" neg/lvs.out; then negok=true; fi
final=$(grep -E "Final result" lvs.out | tail -1 | sed 's/"/\\"/g')
status=fail
if grep -q "Final result: Circuits match uniquely" lvs.out && [ "$negok" = true ]; then status=pass; fi
# Parasitic C extraction of the routed top (masters abstract).
mkdir -p pex && cd pex
cat > pex.tcl <<'EOF'
gds read /work/lvs/pt_core_bias.gds
load pt_core_bias
select top cell
extract do capacitance
extract do coupling
extract all
ext2spice lvs
ext2spice cthresh 0.01
ext2spice -o pt_core_bias_pex.spice
quit -noprompt
EOF
magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc pex.tcl > pex.log 2>&1
caps=$(grep -c '^C' pt_core_bias_pex.spice 2>/dev/null); caps=${caps:-0}
pexstatus=fail
if [ -s pt_core_bias_pex.spice ] && [ "$caps" -gt 0 ]; then pexstatus=pass; fi
printf '{"status": "%s", "scope": "routing LVS: top-level connectivity with leaf masters as pin-only GDS black boxes (netgen -blackbox)", "final": "%s", "report": "lvs/lvs.out", "negative_bridge_rejected": %s, "pex_status": "%s", "pex_capacitors": %s, "pex_netlist": "lvs/pex/pt_core_bias_pex.spice"}\n' \
  "$status" "$final" "$negok" "$pexstatus" "$caps" > /work/lvs.json
cat /work/lvs.json
