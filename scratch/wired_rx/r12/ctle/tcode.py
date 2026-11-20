"""Termination trim code per corner combination (MOS x poly): the pad_hspad a6 code (0-15) whose differential impedance at
20 MHz (PAD_P - PAD_N, R-aware model physical-r-typ.spice, CTLE input loads omitted) is closest to 100 ohm.  The die's
termination is trimmed per die (pads owner), so the chain bench uses this code, not the MOS-corner-only table of rc11.
  tcode.py <ck...>  (through ../../slot.sh)  -> tcode.json"""
import sys, json, re
from pathlib import Path
import r5lib
from r5lib import L, ch10
H = Path(__file__).resolve().parent
out = json.loads((H / 'tcode.json').read_text()) if (H / 'tcode.json').exists() else {}
for ck in sys.argv[1:]:
    res = r5lib.setup('sch')
    c, temp, vdd, bound = L.CORN[ck]
    pad = L.net('pad_hspad', str(ch10.PAD), bound)
    m = dict(DVDD='vdd', VSS='0', VDD='vdd', TERM_VCM='tvcm', TERM_ENABLE='vdd', VBIAS='hvb', RX_P='inp', RX_N='inn', PAD_P='pdp', PAD_N='pdn')
    for b in range(4): m[f'TERM_TRIM{b}'] = f't{b}'
    b = L.hdr(ck, 'tcode') + [f'VTVCM tvcm 0 {ch10.VCM_T}', f'VHVB hvb 0 {ch10.VBIAS}', f'.include {pad}', L.inst('XPAD', pad, 'hs_protected_pad', m),
                              'IAC pdn pdp DC 0 AC 1'] + [f'VT{q} t{q} 0 0' for q in range(4)]
    ctl = ['.control']
    for code in range(16):
        ctl += [f'alter VT{q} dc = {vdd if (code >> q) & 1 else 0}' for q in range(4)]
        ctl += ['ac lin 1 20e6 20e6', 'let zz = mag(v(pdp)-v(pdn))', f'echo ZCODE {code} $&zz']
    b += ctl + ['.endc', '.end']
    log = L.run(f'tcode_{ck}', b, timeout=900)
    z = {int(a): float(v) for a, v in re.findall(r'^ZCODE (\d+) ([-+0-9.eE]+)', log, re.M)}
    best = min(z, key=lambda k: abs(z[k] - 100)) if z else None
    out[ck] = dict(code=best, z_ohm=None if best is None else round(z[best], 1), all={k: round(v, 1) for k, v in z.items()}, rc11_code=r5lib.rc11.TCODE[ck])
    print(ck, out[ck]['code'], out[ck]['z_ohm'], 'rc11', out[ck]['rc11_code'], flush=True)
    (H / 'tcode.json').write_text(json.dumps(out, indent=1))
