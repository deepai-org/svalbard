#!/bin/sh
# Chip-top regression of one chip:  run.sh <rf|wired>   (or <chip>/run.sh). Connectivity checks + self-tests, the bond map,
# the boundary sim with its negative controls and the isolation audit. Exit status is non-zero if anything fails.
# Light: a few seconds for the checks, about a minute for the isolation audit, no SPICE.
cd "$(dirname "$0")" || exit 2
C=$1; [ "$C" = rf ] || [ "$C" = wired ] || { echo "usage: run.sh <rf|wired>"; exit 2; }
shift
P=../..
rc=0
python3 check_top.py $C --selftest || rc=1
python3 check_top.py $C --write "$@" || rc=1
W=${TMPDIR:-/tmp}/pt_top_boundary_$C.$$; mkdir -p "$W"
G=$C/generated
RTL=$P/rtl
python3 sim/gen_defs.py $C > $G/tb_regs.svh || rc=1
SRC="sim/tb_top_boundary.sv $G/pt_analog_top_stub.sv $(ls $RTL/*.sv)"
iverilog -g2012 -I $RTL -I $G -o "$W/pos" -s tb_top_boundary $SRC 2> "$W/cc.log" || { echo "boundary sim: does not compile ($(grep -c error "$W/cc.log") errors)"; head -5 "$W/cc.log"; rc=1; }
vvp "$W/pos" | tee "$W/pos.log" | tail -3
grep -q TOP_BOUNDARY_PASS "$W/pos.log" || { echo "boundary sim: FAIL"; rc=1; }
iverilog -g2012 -DNEG_MISBIND -I $RTL -I $G -o "$W/neg" -s tb_top_boundary $SRC && vvp "$W/neg" > "$W/neg.log"
if grep -q TOP_BOUNDARY_FAIL "$W/neg.log"; then echo "boundary sim negative control (mis-bound bit): detected"; else echo "boundary sim negative control: NOT detected"; rc=1; fi
# negative control on the connectivity itself: swap two probe trim pins in a copy of the conn, regenerate the stub, expect FAIL
python3 -c "import check_top as c; print(c.read_conn('$C/chip.conn'))" > "$W/conn"
if [ $C = rf ]; then sed 's/ ct{0:3}=c_lna_ct\[\\1\]/ ct{0,2,1,3}=c_lna_ct[{0:3}]/' "$W/conn" > "$W/mut.conn"
else sed 's/ ctle_peak{0:2}=c_ctle_peak\[\\1\]/ ctle_peak{0,2,1}=c_ctle_peak[{0:2}]/' "$W/conn" > "$W/mut.conn"; fi
if cmp -s "$W/conn" "$W/mut.conn"; then echo "mutation did not apply"; rc=1; fi
PT_TOP_CONN="$W/mut.conn" PT_TOP_OUT="$W/gen" python3 check_top.py $C --write --no-modewalk > /dev/null
cp $G/tb_regs.svh "$W/gen/"
iverilog -g2012 -I $RTL -I "$W/gen" -o "$W/mut" -s tb_top_boundary sim/tb_top_boundary.sv "$W/gen/pt_analog_top_stub.sv" $(ls $RTL/*.sv) && vvp "$W/mut" > "$W/mut.log"
if grep -q TOP_BOUNDARY_FAIL "$W/mut.log"; then echo "boundary sim negative control (swapped pins in the conn): detected"; else echo "boundary sim negative control (conn): NOT detected"; rc=1; fi
# M6 isolation-state audit (rules K1..K8 of scratch/integration/m6-powerup/audit/iso_audit.py) on the conn, with its self-test
OMP_NUM_THREADS=1 python3 iso_audit_top.py $C --selftest > "$W/iso.log" 2>&1; iso=$?
grep -E "^ISO AUDIT|^  \[K|selftest|macro-internal|RTL facts|Error" "$W/iso.log"
[ $iso = 0 ] || rc=1
rm -rf "$W"
echo "chip-top regression pt_$C: $([ $rc = 0 ] && echo PASS || echo FAIL)"
exit $rc
