#!/bin/bash
# mkprobe.sh <s12 run tag> <new dir> : copy a session-12 d8 data deck and add the wtx_ser8d internal probes
S=../s12/runs/$1/$1_data; D=runs/$2; mkdir -p $D
cp $S/{cmd,mux8,pad,ring,tr7}.spice $S/wtx_ser8d.ext.spice $D/
python3 - "$S/tb.sp" "$D/tb.sp" <<'PY'
import re, sys
s = open(sys.argv[1]).read()
pr = [f'x0.XL{k}__BO' for k in range(8)] + [f'x0.XP{k}__Q' for k in range(8)] + ['x0.XL3__CK', 'x0.XL7__CK', 'x0.XL7__LDA', 'x0.XH5_1__D', 'x0.XH6_1__D', 'x0.XH7_1__D'] + [f'F{k}' for k in range(8)] + [f'PH{a}' for a in (45, 90, 135, 180, 225, 270, 315)]
add = ''.join(f' v({p})' for p in pr)
s = re.sub(r'^(save .*)$', lambda m: m.group(1) + add, s, flags=re.M)
s = re.sub(r'^(wrdata .*)$', lambda m: m.group(1) + add, s, flags=re.M)
if len(sys.argv) > 3:
    s = re.sub(r'^\.tran (\S+) (\S+)', lambda m: f'.tran {m.group(1)} {sys.argv[3]}', s, flags=re.M)
open(sys.argv[2], 'w').write(s)
PY
