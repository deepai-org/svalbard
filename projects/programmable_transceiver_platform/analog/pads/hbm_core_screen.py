"""PD28 item 3: HBM-like screen of the CORE-side gates reachable from each custom pad (pads owner).

Same bench as stress_safe_family_sims (HBM-like 2 kV: 1.33 A peak, 2 ns rise, 150 ns decay, unpowered bare die,
VDD held at 0 V through 1 ohm with 100 nF), plus the consumer block(s) that the chip netlist
(verification/chip_assembly/netlist.py PATHS) attaches to the pad nets, flattened from their published
extracted netlists. Every MOS of every consumer is fully observed; the gate-terminal screen is the
unchanged spec limit (spec/schematic-implementation.json: 3.63 V for 3.3 V devices, 6.0 V for 6 V).
Unbound consumer ports: supplies -> the unpowered VDD node, VSS -> 0, all other ports 100 kohm to 0
(unpowered drivers). Compact-model diagnostic, not HBM qualification (same caveat as PD13).
    python3 hbm_core_screen.py <case> [<case> ...]   -> out/<case>.json
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

PADS = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
A = PADS.parent
sys.path.insert(0, str(PADS))
import stress_safe_family_sims as f  # noqa: E402
import stress_safe_clamp as s  # noqa: E402

HERE = Path(os.environ.get('HBM_CORE_DIR', '/home/ubuntu/svalbard/scratch/pads-pd28/hbm_core'))   # sims and per-case outputs (scratch)
G = PADS / 'generated/stress-safe-families'
MOS = {'nfet_03v3', 'pfet_03v3', 'nfet_06v0', 'pfet_06v0', 'nfet_06v0_nvt', 'nfet_05v0', 'pfet_05v0'}
import os  # noqa: E402
JUNCTION = os.environ.get('HBM_CORE_JUNCTION') == '1'
SUPPLY = re.compile(r'^(VDD.*|RAIL.*|VDD_WIRE_SW)$', re.I)

RFPAIR_GC = Path('/home/ubuntu/svalbard/scratch/pads-pd12/v2/rf-pair/pad-extracted.spice')   # the compact GC rf_pair published by PD28 (item 6)
# case: pad family model (family key for safe_deck), pad-side node per consumer port, consumers
# PD48 (ESD tiering): transient gate-oxide limit for the ~150 ns HBM pulse, derived in spec/design-assumptions.md
# ("Gate oxide transient limit"): pessimistic tox (model nominal - corner - 3 sigma) and a TDDB budget of <= 1000
# events x 200 ns; 3.3 V oxide 5.0 V, 6 V oxide 8.0 V, 5 V oxide 7.0 V. HBM_CORE_DC_LIMITS=1 restores the DC screen.
TRANSIENT_LIMITS = {'nfet_03v3': 5.0, 'pfet_03v3': 5.0, 'nfet_06v0': 8.0, 'pfet_06v0': 8.0, 'nfet_06v0_nvt': 8.0, 'nfet_05v0': 7.0, 'pfet_05v0': 7.0}
# HBM level per case (MANDATE ESD tiering): RF_RX and debug/ATB pads stay 2 kV; RF_TX, WIRE_TX, USB/wired RX 1 kV;
# clocks/REF/AUX are 1 kV optional -> screened at 2 kV (HBM_CORE_KV overrides every case).
# Drain-source (snapback/BVdss) screen during the pulse, pessimistic (GGNMOS Vt1 of 3.3 V devices ~6-7 V, 6 V devices
# ~10-12 V in comparable 180 nm processes; no GF180 TLP data): 5.5 V / 9.0 V. Literature-based, confidence L.
VDS_LIMITS = {'nfet_03v3': 5.5, 'pfet_03v3': 5.5, 'nfet_06v0': 9.0, 'pfet_06v0': 9.0, 'nfet_06v0_nvt': 9.0, 'nfet_05v0': 8.0, 'pfet_05v0': 8.0}
TIER_KV = {'rf_rx_lna': 2, 'rf_rx_lna_compact_gc': 2, 'bb_tap': 2, 'wmon_bb_tap': 2, 'rf_tx_rfdriver': 1, 'wire_tx_detect': 1,
           'wirepad_rx_core': 1, 'aux_clk': 2, 'wclk_wtx_ext': 2, 'ref_lo_ext': 2}
CASES = {
    'rf_rx_lna': dict(family='rfpad', model=G / 'rf-pair/pad-extracted.spice',
                      consumers=[(A / 'rf_rx/generated/lna.ext.spice', 'pt_lna', {'rf_in_p': 'PAD_P', 'rf_in_n': 'PAD_N'})]),
    'rf_rx_lna_compact_gc': dict(family='rfpad', model=Path('/home/ubuntu/svalbard/scratch/pads-pd12/v2/rf-pair/pad-extracted.spice'),
                                 consumers=[(A / 'rf_rx/generated/lna.ext.spice', 'pt_lna', {'rf_in_p': 'PAD_P', 'rf_in_n': 'PAD_N'})]),
    'rf_tx_rfdriver': dict(family='rfpad', model=G / 'rf-tx/pad-extracted.spice',
                           consumers=[(A / 'rf_tx/generated/rfdriver.ext.spice', 'pt_rfdriver', {'pad_p': 'PAD_P', 'pad_n': 'PAD_N'})]),
    'bb_tap': dict(family='rfpad', model=RFPAIR_GC,
                   consumers=[(A / 'rf_rx/generated/bb_tap.ext.spice', 'pt_bb_tap', {'pad_p': 'PAD_P', 'pad_n': 'PAD_N'})]),
    'aux_clk': dict(family='rfpad', model=RFPAIR_GC,
                    consumers=[(A / 'timing/generated/lo_ext.ext.spice', 'pt_lo_ext', {'EXT_QP': 'PAD_P', 'EXT_QN': 'PAD_N'}),
                               (A / 'timing/generated/diff_clk_rx.ext.spice', 'pt_diff_clk_rx', {'INP': 'PAD_P', 'INN': 'PAD_N'})]),
    'wclk_wtx_ext': dict(family='rfpad', model=RFPAIR_GC,
                         consumers=[(A / 'timing/generated/diff_clk_rx.ext.spice', 'pt_diff_clk_rx', {'INP': 'PAD_P', 'INN': 'PAD_N'})]),
    'ref_lo_ext': dict(family='refpad', model=G / 'reference/physical.spice',
                       consumers=[(A / 'timing/generated/lo_ext.ext.spice', 'pt_lo_ext', {'EXT_IP': 'PAD_P', 'EXT_IN': 'PAD_N'})]),
    'wmon_bb_tap': dict(family='rfpad', model=G / 'single-leg/pad-extracted.spice',
                        consumers=[(A / 'rf_rx/generated/bb_tap.ext.spice', 'pt_bb_tap', {'pad_p': 'PAD_P', 'pad_n': 'VSS'})]),
    'wire_tx_detect': dict(family='txpad', model=G / 'wired-transmit/physical.spice',
                           consumers=[(A / 'wired_rx/generated/detect.ext.spice', 'pt_detect', {'TX_P': 'PAD_P', 'TX_N': 'PAD_N'})]),
    'wirepad_rx_core': dict(family='wirepad', model=G / 'wired-receive-usb/physical.spice',
                            consumers=[(A / 'wired_rx/generated/ctle.ext.spice', 'pt_ctle', {'RX_P': 'RX_P', 'RX_N': 'RX_N'}),
                                       (A / 'wired_rx/generated/rxselect.ext.spice', 'pt_rxselect', {'RX_P': 'RX_P', 'RX_N': 'RX_N'}),
                                       (A / 'wired_rx/generated/detect.ext.spice', 'pt_detect', {'RX_P': 'RX_P', 'RX_N': 'RX_N'}),
                                       (A / 'wired_rx/generated/wmon_sel.ext.spice', 'pt_wmon_sel', {'RX_P': 'RX_P', 'RX_N': 'RX_N'})]),
}


def clean(tok):
    return tok if '=' in tok else re.sub(r'[#/\[\]<>:]', '_', tok)


def subckts(text):
    text = re.sub(r'\n\+\s*', ' ', text)
    out, cur = {}, None
    for l in text.splitlines():
        t = l.split()
        if not t or l.startswith('*'):
            continue
        if t[0].lower() == '.subckt':
            cur = t[1]; out[cur] = dict(ports=[clean(x) for x in t[2:] if '=' not in x], body=[])
        elif t[0].lower() == '.ends':
            cur = None
        elif cur:
            out[cur]['body'].append([clean(x) for x in t])
    return out


def flatten(defs, top, binding, prefix, lines, mos):
    """Emit top-level lines for subckt `top` with port->net `binding`; internal nets get `prefix`."""
    d = defs[top]
    net = lambda n: '0' if n in ('0', 'gnd', 'GND') else binding.get(n, prefix + n)  # noqa: E731
    for t in d['body']:
        k = t[0][0].upper()
        if k == 'X':
            nodes = [x for x in t[1:] if '=' not in x]
            model = nodes[-1]; nodes = nodes[:-1]; params = [x for x in t[1:] if '=' in x]
            if model in defs:
                sub = defs[model]
                flatten(defs, model, dict(zip(sub['ports'], [net(n) for n in nodes])), prefix + t[0] + '_', lines, mos)
            else:
                nn = [net(n) for n in nodes]
                lines.append(' '.join([f'X{prefix}{t[0]}'] + nn + [model] + params))
                if model in MOS:
                    mos.append(dict(name=prefix + t[0], model=model, D=nn[0], G=nn[1], S=nn[2], B=nn[3]))
        elif k in 'RC':
            lines.append(' '.join([f'{k}{prefix}{t[0]}', net(t[1]), net(t[2])] + t[3:]))
        elif k == 'D':
            lines.append(' '.join([f'D{prefix}{t[0]}', net(t[1]), net(t[2])] + t[3:]))
        else:
            raise ValueError(f'unsupported element {t[0]} in {top}')


def consumer_block(case):
    lines, mos = [], []
    for k, (path, top, bind) in enumerate(CASES[case]['consumers']):
        defs = subckts(path.read_text())
        ports = defs[top]['ports']
        b = {}
        for p in ports:
            if p in bind:
                b[p] = bind[p]
            elif p == 'VSS' or p.upper() == 'VSUBS':
                b[p] = '0'
            elif SUPPLY.match(p):
                b[p] = 'VDD'
            else:
                b[p] = f'U{k}_{p}'
                lines.append(f'RU{k}_{p} U{k}_{p} 0 100k')
                if JUNCTION:   # the unpowered driving block's output drain junctions (10 um2 n+/psub and p+/nwell=VDD)
                    lines.append(f'DUN{k}_{p} 0 U{k}_{p} diode_nd2ps_03v3 area=10e-12 pj=14e-6')
                    lines.append(f'DUP{k}_{p} U{k}_{p} VDD diode_pd2nw_03v3 area=10e-12 pj=14e-6')
        flatten(defs, top, b, f'c{k}_', lines, mos)
    return '\n'.join(lines) + '\n', mos


def run(case, hbm_case, process, temp_c):
    c = CASES[case]
    f.DRAWN_SHUNT = True
    f.FAMILIES[c['family']] = dict(f.FAMILIES[c['family']], model=c['model'])
    tag = case + ('_jn' if JUNCTION else '')
    work = HERE / 'work' / tag
    name = f'{tag}_{hbm_case}_{process}_{temp_c}'
    f.HBM_KV = float(os.environ.get('HBM_CORE_KV', TIER_KV.get(case, 2)))
    deck, ports, stop = f.safe_deck(c['family'], hbm_case, process, temp_c, work, name)
    deck = deck[:deck.index('.control')]
    block, mos = consumer_block(case)
    nodes = sorted({m[t] for m in mos for t in 'DGSB'} - {'0'})
    vec = ['v(PAD_P)', 'v(PAD_N)' if 'PAD_N' in ports else 'v(PAD_P)'] + [f'v({n})' for n in nodes]
    deck += block + '.option method=gear\n' + s.control(work, name, 'tran .05n 600n', ' '.join(vec))
    x = s.run(work, name, deck, timeout_s=3600)
    if not np.isfinite(x).all() or x[-1, 0] < stop * .999:
        return dict(case=case, hbm=hbm_case, process=process, temp_c=temp_c, complete=False)
    val = {n: x[:, 3 + i] for i, n in enumerate(nodes)}
    val['0'] = np.zeros(len(x))
    limits = TRANSIENT_LIMITS if not os.environ.get('HBM_CORE_DC_LIMITS') else dict(s.gate_limits()[0], nfet_06v0_nvt=6.0, nfet_05v0=5.5, pfet_05v0=5.5)
    rows = []
    for m in mos:
        g = max(float(np.max(np.abs(val[m['G']] - val[m[t]]))) for t in 'DSB')
        ds = float(np.max(np.abs(val[m['D']] - val[m['S']])))
        rows.append(dict(device=m['name'], model=m['model'], gate_v=round(g, 3), vds_v=round(ds, 3),
                         exceeds=g > limits[m['model']] or (not os.environ.get('HBM_CORE_DC_LIMITS') and ds > VDS_LIMITS[m['model']]),
                         exceeds_vds=ds > VDS_LIMITS[m['model']], nodes={t: m[t] for t in 'DGSB'}))
    rows.sort(key=lambda r: -r['gate_v'] / limits[r['model']])
    bad = [r for r in rows if r['exceeds']]
    import hashlib
    return dict(case=case, hbm_kv=f.HBM_KV, limits=limits, vds_limits=VDS_LIMITS, worst_vds=max(rows, key=lambda r: r['vds_v'] / VDS_LIMITS[r['model']]),
                consumer_sha256={str(p_): hashlib.sha256(Path(p_).read_bytes()).hexdigest() for p_, *_ in c['consumers']},
                pad_model_sha256=hashlib.sha256(Path(c['model']).read_bytes()).hexdigest(), junction_model=JUNCTION, hbm=hbm_case, process=process, temp_c=temp_c, complete=True,
                pad_p_range_v=[float(x[:, 1].min()), float(x[:, 1].max())], pad_n_range_v=[float(x[:, 2].min()), float(x[:, 2].max())],
                consumer_mos=len(rows), exceeding=len(bad), worst=rows[:8],
                exceeding_devices=sorted({(r['model'], r['nodes']['G']) for r in bad}),
                op_fallback=f.op_fallback(work, name), model=str(c['model']))


if __name__ == '__main__':
    # P_pos at tt/27 and ss/0 (ss/0 is the highest pad peak in every PD13/PD21 family run), P_neg at ss/0
    matrix = [('hbm_P_pos', 'typical', 27), ('hbm_P_pos', 'ss', 0), ('hbm_P_pos', 'ff', 85), ('hbm_P_neg', 'ss', 0)]   # PD48: + ff/85
    for case in sys.argv[1:]:
        out = []
        for hc, p, t in matrix:
            if True:
                try:
                    r = run(case, hc, p, t)
                except Exception as e:  # recorded, never hidden
                    r = dict(case=case, hbm=hc, process=p, temp_c=t, error=repr(e)[:600])
                out.append(r)
                print(json.dumps({k: r.get(k) for k in ('case', 'hbm', 'process', 'temp_c', 'pad_p_range_v', 'consumer_mos', 'exceeding', 'error')}), flush=True)
                (HERE / 'out').mkdir(exist_ok=True)
                (HERE / 'out' / f"{case}{'_jn' if JUNCTION else ''}{os.environ.get('HBM_CORE_TAG', '')}.json").write_text(json.dumps(out, indent=1, default=list))
