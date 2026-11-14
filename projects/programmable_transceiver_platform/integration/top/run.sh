#!/bin/sh
# One command for the chip-top regression: connectivity checks + self-tests + the boundary sim with its negative control.
# Exit status is non-zero if anything fails. Light: a few seconds, no SPICE.
cd "$(dirname "$0")" || exit 2
P=../..
rc=0
python3 check_top.py --selftest || rc=1
python3 check_top.py --write "$@" || rc=1
W=${TMPDIR:-/tmp}/pt_top_boundary.$$; mkdir -p "$W"
# Boundary sim on the working-tree RTL: the macro presents every c_* / s_* port by name (TOP-1 done by digital 2026-11-14).
RTL=$P/rtl
python3 sim/gen_defs.py > generated/tb_regs.svh || rc=1
iverilog -g2012 -I $RTL -I generated -o "$W/pos" -s tb_top_boundary sim/tb_top_boundary.sv generated/pt_analog_top_stub.sv $(ls $RTL/*.sv) 2> "$W/cc.log" || { echo "boundary sim: rtl/ does not compile ($(grep -c error "$W/cc.log") errors)"; rc=1; }
SRC="sim/tb_top_boundary.sv generated/pt_analog_top_stub.sv $(ls $RTL/*.sv)"
vvp "$W/pos" | tee "$W/pos.log" | tail -3
grep -q TOP_BOUNDARY_PASS "$W/pos.log" || { echo "boundary sim: FAIL"; rc=1; }
iverilog -g2012 -DNEG_MISBIND -I $RTL -I generated -o "$W/neg" -s tb_top_boundary $SRC && vvp "$W/neg" > "$W/neg.log"
if grep -q TOP_BOUNDARY_FAIL "$W/neg.log"; then echo "boundary sim negative control (mis-bound bit): detected"; else echo "boundary sim negative control: NOT detected"; rc=1; fi
# negative control on the connectivity itself: swap lna ct1/ct2 in a copy of the conn, regenerate the stub, expect FAIL
sed 's/ ct{0:3}=c_lna_ct\[\\1\]/ ct{0,2,1,3}=c_lna_ct[{0:3}]/' pt_chip.conn > "$W/mut.conn"
if cmp -s pt_chip.conn "$W/mut.conn"; then echo "mutation did not apply"; rc=1; fi
PT_TOP_CONN="$W/mut.conn" PT_TOP_OUT="$W/gen" python3 check_top.py --write --no-modewalk > /dev/null
cp generated/tb_regs.svh "$W/gen/"
iverilog -g2012 -I $RTL -I "$W/gen" -o "$W/mut" -s tb_top_boundary sim/tb_top_boundary.sv "$W/gen/pt_analog_top_stub.sv" $(ls $RTL/*.sv) && vvp "$W/mut" > "$W/mut.log"
if grep -q TOP_BOUNDARY_FAIL "$W/mut.log"; then echo "boundary sim negative control (swapped pins in the conn): detected"; else echo "boundary sim negative control (conn): NOT detected"; rc=1; fi
# M6 isolation-state audit (rules K1..K8 of scratch/integration/m6-powerup/audit/iso_audit.py) on the conn, with its self-test
OMP_NUM_THREADS=1 python3 iso_audit_top.py --selftest > "$W/iso.log" 2>&1; iso=$?
grep -E "^ISO AUDIT|^  \[K|selftest|macro-internal|RTL facts" "$W/iso.log"
[ $iso = 0 ] || rc=1
rm -rf "$W"
echo "chip-top regression: $([ $rc = 0 ] && echo PASS || echo FAIL)"
exit $rc
