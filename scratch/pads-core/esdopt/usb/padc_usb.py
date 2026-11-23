"""padc_usb.py (esdopt/usb, copy of scratch/pads-pd46/usb/padc.py 2026-11-20): usage padc_usb.py <model> <tag>; model loader accepts
the option-A model (no ESD_RAIL, inner combined_flat), DVDD (ring supply) held at VDD, output bench/<tag>-padc.json. Original:
PD45 USB pad C including the bypass-on RX load (PD41 nit). Published pad_wirepad extraction, controls off except
BYPASS_ENABLE (and, case 'hsrx', TERM_ENABLE as in USB HS receive); RX_P/N drive the EXTRACTED pt_rxselect (enabled,
direct), pt_detect (enabled) and pt_wmon_sel (enabled = worst) exactly as USB_RX_P/N connect at integration
(wired_rx README item 9). Small-signal C at 1 GHz on PAD_P, PAD_N AC-grounded, at the pad DC bias given."""
import sys, json, re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
P = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog'
sys.path.insert(0, P + '/pads')
import stress_safe_usb as u, stress_safe_clamp as s
TAG = sys.argv[2]; W = Path(__file__).resolve().parent / 'benchrun' / ('padc_' + TAG); W.mkdir(parents=True, exist_ok=True)
import stress_safe_family_sims as f
from loading_audit import anchor_floating_conductors
_mt = f.model_text
def model_text(family):
    text = re.sub(r'\n\+\s*', ' ', f.FAMILIES[family]['model'].read_text())
    if 'ESD_RAIL' in text.split('.subckt combined_flat ', 1)[1].split('\n', 1)[0]: return _mt(family)
    text = '\n'.join(l for l in text.splitlines() if not l.startswith('.lib '))
    text = re.sub(r'#(?=[\s=)]|$)', '_h', text, flags=re.M)
    body, _ = anchor_floating_conductors(text + '\n', 1e12)
    wrap = next(l for l in body.splitlines() if l.startswith('.subckt tx_protected_pad '))
    return body, wrap.split()[1], wrap.split()[2:]
f.model_text = model_text
MODEL = Path(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else Path(P) / 'pads/generated/stress-safe-families/wired-receive-usb/physical.spice'
u.WIREPAD_MODEL = MODEL.resolve()
G = Path(P) / 'wired_rx/generated'
RXL = Path('/home/ubuntu/svalbard/scratch/pads-pd46/usb/rxload')   # PD46: current wired_rx extractions (detect changed since PD45)
def ports(path, name):
    t = path.read_text().replace('\n+', ' ')
    return re.search(rf'^\.subckt {name} (.*)$', t, re.M).group(1).split()
BL = [('rxselect', 'pt_rxselect'), ('detect', 'pt_detect'), ('wmon_sel', 'pt_wmon_sel')]
ON = {'rxselect_en', 'rxselect_direct', 'det_en', 'wmon_en'}
def deck(p, t, v, bias, rxload, mode, leg='P'):
    name = f'padc_{mode}_{"rx" if rxload else "norx"}_{p}_{t}_{bias}_{leg}'
    d, _ = u.deck('cap', p, t, v, W, name)
    d = d.replace('VDVDD DVDD 0 0\n', f'VDVDD DVDD 0 {v}\n')
    src = (f'VACP PAD_P 0 DC {bias} AC 1\nVACN PAD_N 0 DC {bias}' if leg == 'P' else f'VACP PAD_N 0 DC {bias} AC 1\nVACN PAD_P 0 DC {bias}')
    assert 'VACP PAD_P 0 DC 1.65 AC 1\nVACN PAD_N 0 DC 1.65' in d
    d = d.replace('VACP PAD_P 0 DC 1.65 AC 1\nVACN PAD_N 0 DC 1.65', src)
    d = d.replace('VBYPASS_ENABLE BYPASS_ENABLE 0 0', f'VBYPASS_ENABLE BYPASS_ENABLE 0 {v}')
    if mode == 'hsrx':
        d = d.replace('VTERM_ENABLE TERM_ENABLE 0 0', f'VTERM_ENABLE TERM_ENABLE 0 {v}')
    if rxload:
        d = '\n'.join(l for l in d.splitlines() if not l.startswith(('CCORE_', 'RCORE_')))
        add = []
        for f, sub in BL:
            add.append(f'.include {RXL}/{f}.ext.spice')
            nodes = []
            for q in ports(G / f'{f}.ext.spice', sub):
                if q in ('RX_P', 'RX_N'): nodes.append(q)
                elif q == 'VDD_WIRE_SW': nodes.append('VDD')
                elif q == 'VSS': nodes.append('0')
                elif q in ON: nodes.append('VDD')
                elif q == 'IBIAS': nodes.append(f'{f}_IBIAS')
                else: nodes.append(f'{f}_{q}')
            add.append(f'X{f} ' + ' '.join(nodes) + f' {sub}')
            if f == 'detect': add.append('IDETB VDD detect_IBIAS 10u')
            for q in ports(G / f'{f}.ext.spice', sub):
                if q not in ('RX_P', 'RX_N', 'VDD_WIRE_SW', 'VSS', 'IBIAS') and q not in ON:
                    add.append(f'R{f}_{q} {f}_{q} 0 1meg')
        d = d.replace('\nXpad ', '\n' + '\n'.join(add) + '\nXpad ', 1)
    assert f'VBYPASS_ENABLE BYPASS_ENABLE 0 {v}' in d
    return name, d
jobs = []
import os
for p, t, v in [c for c in (('typical', 27, 3.3), ('ss', 22, 3.15), ('ss', 32, 3.15), ('ff', 22, 3.35), ('ff', 32, 3.35)) if not os.environ.get('CORN') or f'{c[0]}_{c[1]}' in os.environ['CORN']]:
    for bias in (0.2, 1.65):
        for leg in 'PN':
            for mode in ('off', 'hsrx'):   # off = BYPASS_ENABLE only; hsrx = USB HS receive (bypass + termination)
                jobs.append(deck(p, t, v, bias, True, mode, leg))
def go(j):
    name, d = j
    x = np.atleast_2d(s.run(W, name, d, timeout_s=3600))
    y = complex(x[0, 1], x[0, 2])
    return name, dict(c_pf=abs(y.imag) / (2 * np.pi * 1e9) * 1e12, g_s=abs(y.real))
with ThreadPoolExecutor(1) as ex:
    res = dict(ex.map(go, jobs))
for k, r in res.items(): print(k, r)
(Path(__file__).resolve().parent / 'bench').mkdir(exist_ok=True)
(Path(__file__).resolve().parent / 'bench' / f'{TAG}-padc.json').write_text(json.dumps(dict(model=str(MODEL), model_sha256=s.sha(MODEL), results=res), indent=1))
for q in W.glob('*.dat'): q.unlink()
