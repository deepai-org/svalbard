#!/bin/sh
# One command for the chip-top regression: connectivity checks + self-tests + the boundary sim with its negative control.
# Exit status is non-zero if anything fails. Light: a few seconds, no SPICE.
cd "$(dirname "$0")" || exit 2
P=../..
rc=0
python3 check_top.py --selftest || rc=1
python3 check_top.py --write "$@" || rc=1
W=${TMPDIR:-/tmp}/pt_top_boundary.$$; mkdir -p "$W"
# RTL for the boundary sim: the working tree if it compiles, else the last committed rtl/ + register map (the digital
# owner's rework can leave the tree uncompilable for hours; the sim then says which RTL it used)
RTL=$P/rtl; MAP=$P/spec/register-map.json; RTLSRC="working tree"
python3 sim/gen_defs.py $MAP > generated/tb_regs.svh 2>/dev/null
if ! iverilog -g2012 -I $RTL -I generated -o "$W/pos" -s tb_top_boundary sim/tb_top_boundary.sv generated/pt_analog_top_stub.sv $(ls $RTL/*.sv) 2> "$W/cc.log"; then
  mkdir -p "$W/head"; (cd $P && git archive HEAD rtl spec/register-map.json) | tar -x -C "$W/head"
  RTL="$W/head/rtl"; MAP="$W/head/spec/register-map.json"; RTLSRC="git HEAD (working-tree rtl/ does not compile: $(grep -c error "$W/cc.log") errors)"
  python3 sim/gen_defs.py $MAP > generated/tb_regs.svh || rc=1
  iverilog -g2012 -I $RTL -I generated -o "$W/pos" -s tb_top_boundary sim/tb_top_boundary.sv generated/pt_analog_top_stub.sv $(ls $RTL/*.sv) || rc=1
fi
echo "boundary sim RTL: $RTLSRC"
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
rm -rf "$W"
echo "chip-top regression: $([ $rc = 0 ] && echo PASS || echo FAIL)"
exit $rc
