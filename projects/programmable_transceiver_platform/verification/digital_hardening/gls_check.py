#!/usr/bin/env python3
"""Check the macro-level gate-level simulation (gls.sh output).

1. Lockstep: the post-route netlist log equals the RTL macro log record by record (every SPI
   read, every snapshot of every macro output), X/Z included.
2. Reference model: every SPI read and every regfile-visible snapshot field of the netlist
   equals the generated register-map model (verification/check_regfile.py), except reads whose
   model value is a bench constant of tb_regfile (legacy STATUS 0x03, capture data 0x25/0x26,
   checker status registers) and the raw observation-mux values (those are covered by 1).
3. Reset safety: in every snapshot taken while reset is asserted (initial RESET_N+POR, RESET_N
   alone, POR alone, RESET_N in the middle of a write) every output to analog / pads is at its
   safe value and no output is X/Z, except the two data buses whose valid is 0
   (wire_tx_data, rf_tx_sample: FIFO storage has no reset; reported).
4. Observability: directed SPI reads of ID/ABI/map hash, reset-cause flags (POR vs RESET_N),
   island power-good and fault status.
"""
import argparse
import json
from pathlib import Path

EXTRA = ['rf_trim', 'wire_trim', 'clock_trim', 'calibration_trial', 'wire_tx_valid', 'wire_idle', 'rf_tx_valid',
         'rf_mute', 'wire_tx_data', 'rf_tx_sample', 'd2h_oe', 'd2h_clk_pin', 'd2h_sl', 'd2h_pdrv_pin', 'ct_bits',
         'ct_det_div', 'island_on', 'atb_grp_en']
SAFE = {'rf_trim': '0000', 'wire_trim': '0000', 'clock_trim': '0000', 'calibration_trial': '000',
        'wire_tx_valid': '0', 'wire_idle': '1', 'rf_tx_valid': '0', 'rf_mute': '1', 'd2h_oe': '0',
        'd2h_clk_pin': '0', 'ct_bits': '0000000000', 'island_on': '00', 'atb_grp_en': '000'}
DATA_QUALIFIED = ('wire_tx_data', 'rf_tx_sample')


def parse(path):
    recs = []
    for ln in Path(path).read_text().splitlines():
        t = ln.split()
        if not t:
            continue
        if t[0] == 'S':
            bar = t.index('|')
            recs.append(('S', t[1], t[2:bar], dict(zip(EXTRA, t[bar + 1:]))))
        elif t[0] == 'R':
            recs.append(('R', int(t[1], 16), t[2]))
        elif t[0] == 'E':
            recs.append(('E', int(t[1])))
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out)
    exp = json.loads((out / 'expect.json').read_text())
    res = dict(status='fail')
    try:
        rtl, gl = parse(out / 'regfile/rtl/tb.log'), parse(out / 'regfile/gl/tb.log')
    except FileNotFoundError as e:
        res['error'] = str(e)
        (out / 'gls-report.json').write_text(json.dumps(res, indent=1) + '\n')
        print(json.dumps(res, indent=1))
        return 1
    # 1. lockstep
    lock = [i for i, (x, y) in enumerate(zip(rtl, gl)) if x != y]
    if len(rtl) != len(gl):
        lock.append(f'length {len(rtl)} vs {len(gl)}')
    res['lockstep'] = dict(records_rtl=len(rtl), records_gl=len(gl), mismatches=len(lock),
                           first=[str(rtl[i]) + ' / ' + str(gl[i]) for i in lock[:5] if isinstance(i, int)])
    # 2. model
    body = [r for r in gl if r[0] in ('S', 'R')]
    model = [('S', 'R0', exp['reset_snapshot'])] + [tuple(e) for e in exp['expect']]
    skip_reads = {0x03, 0x25, 0x26} | set(exp['status_addrs'])  # incl. status.pll_lock: checked in 4.
    mm, n_reads, n_snaps, skipped = [], 0, 0, 0
    for got, e in zip(body, model):
        if e[0] == 'R':
            if got[0] != 'R' or got[1] != e[1]:
                mm.append(f'record order at read 0x{e[1]:02X}: {got}')
                continue
            if e[1] in skip_reads:
                skipped += 1
                continue
            n_reads += 1
            if any(ch in 'xXzZ' for ch in got[2]) or int(got[2], 16) != e[2]:
                mm.append(f'read 0x{e[1]:02X}: got {got[2]} expected 0x{e[2]:04X}')
        else:
            if got[0] != 'S' or got[1] != e[1]:
                mm.append(f'record order at snapshot {e[1]}: {got[:2]}')
                continue
            n_snaps += 1
            f, m = got[2], e[2]
            if any(ch in 'xXzZ' for tok in f for ch in tok):
                mm.append(f'snapshot {e[1]}: X/Z in regfile fields')
                continue
            g = dict(island_on=int(got[3]['island_on'], 16), analog_cfg=int(f[0], 16), debug_cfg=int(f[1], 16), island_en=int(f[2], 16), atb0=int(f[3], 16),
                     atb1=int(f[4], 16), rx_oe=f[5], obs_oe=f[6][1] + f[6][3] + f[6][5], toggle=f[7],
                     enable=int(f[8], 16), mode8=int(f[9], 16), miso_oe=int(f[10]), miso=int(f[11]))
            w = dict(island_on=m[3], analog_cfg=m[0], debug_cfg=m[1], island_en=m[2], atb0=m[4], atb1=m[5], rx_oe=m[6],
                     obs_oe=m[7][1] + m[7][3] + m[7][5], toggle=m[8][0], enable=m[9], mode8=m[10], miso_oe=m[12],
                     miso=m[13])
            diff = [k for k in g if g[k] != w[k]]
            if diff:
                mm.append(f'snapshot {e[1]} #{n_snaps}: differs in {diff}')
    if len(body) != len(model):
        mm.append(f'{len(body)} records vs {len(model)} expected')
    res['model'] = dict(reads_checked=n_reads, reads_skipped_bench_constant=skipped, snapshots_checked=n_snaps,
                        mismatches=len(mm), first=mm[:10])
    # 3. reset safety
    reset_tags = ('R0', 'RST', 'POR', 'MID')
    rs, viol, xdata = 0, [], set()
    for r in gl:
        if r[0] != 'S' or r[1] not in reset_tags:
            continue
        rs += 1
        f, x = r[2], r[3]
        if f[0] != format(exp['reset_snapshot'][0], 'x').zfill(len(f[0])) and int(f[0], 16) != exp['reset_snapshot'][0]:
            viol.append(f'{r[1]}: analog_cfg not at reset default')
        if int(f[1], 16) != exp['reset_snapshot'][1]:
            viol.append(f'{r[1]}: debug_cfg not at reset default')
        for k, idx in (('island_en', 2), ('atb0', 3), ('atb1', 4)):
            if int(f[idx], 16) != 0:
                viol.append(f'{r[1]}: {k} != 0')
        if f[5] != '00000' or f[6] != '000000' or int(f[8], 16) or int(f[9], 16) or f[11] != '0':
            viol.append(f'{r[1]}: enables/observation/miso not safe {f[5:12]}')
        if r[1] != 'MID' and f[10] != '0':
            viol.append(f'{r[1]}: miso_oe with CS_N high')
        for k, v in SAFE.items():
            if x[k] != v:
                viol.append(f'{r[1]}: {k}={x[k]} (safe {v})')
        if x['d2h_pdrv_pin'][1:] != '00':  # d2h_pin[9:0] (low 10 bits of the 12-bit field)
            viol.append(f'{r[1]}: d2h_pin {x["d2h_pdrv_pin"]}')
        for k in x:
            if k in DATA_QUALIFIED:
                if any(ch in 'xXzZ' for ch in x[k]):
                    xdata.add(k)
            elif any(ch in 'xXzZ' for ch in x[k]):
                viol.append(f'{r[1]}: {k} X/Z')
        if any(ch in 'xXzZ' for tok in f for ch in tok):
            viol.append(f'{r[1]}: X/Z in regfile outputs')
    res['reset_safety'] = dict(reset_snapshots=rs, violations=len(viol), first=viol[:10],
                               x_on_data_with_valid_low=sorted(xdata), safe_values=SAFE,
                               regfile_fields='analog_cfg/debug_cfg at reset defaults; island_en, ATB, receiver and '
                                              'observation enables, ENABLE, MODE8 0; MISO 0 and MISO_OE 0 with CS_N high')
    # 4. observability (directed tail): values in the GL log
    reads = [r for r in gl if r[0] == 'R']
    tail = reads[-11:]
    names = ['ID', 'ABI', 'MAP_HASH', 'RESET_STATUS after POR', 'RESET_STATUS after W1C', 'RESET_STATUS after RESET_N',
             'ISLAND_STATUS pgood=0x2A', 'FAULT_STATUS fault=1', 'ISLAND_STATUS pgood=0', 'FAULT_STATUS fault=0',
             'STATUS (ENABLE=1, clocks running)']
    # directed tail: 12 observability reads, then (after commit read-backs) the two PLL-lock reads
    lockr = [r for r in reads if r[1] == exp['pll_lock_addr']][-2:]
    cnt = [r for r in reads if r[1] == exp['pll_lock_addr'] + 1][-1:]
    idx = max(i for i, r in enumerate(reads) if r[1] == 0x03)
    pre = reads[idx - 11:idx]
    obs = {n: r[2] for n, r in zip(names, pre)}
    obs['STATUS (ENABLE=0, after run)'] = reads[idx][2]
    obs['FREQ_COUNT_A lock (source=REF, target 256)'] = lockr[0][2] if lockr else None
    obs['FREQ_COUNT_A count'] = cnt[0][2] if cnt else None
    obs['FREQ_COUNT_A lock (source=off)'] = lockr[1][2] if len(lockr) > 1 else None
    want = {'ID': exp['id'], 'ABI': exp['abi'], 'MAP_HASH': exp['map_hash'], 'RESET_STATUS after POR': 3,
            'RESET_STATUS after W1C': 0, 'RESET_STATUS after RESET_N': 2, 'ISLAND_STATUS pgood=0x2A': 0x2A00,
            'FAULT_STATUS fault=1': 1, 'ISLAND_STATUS pgood=0': 0, 'FAULT_STATUS fault=0': 0,
            'FREQ_COUNT_A lock (source=REF, target 256)': 1 << exp['pll_lock_lsb']['locked'],
            'FREQ_COUNT_A count': 256, 'FREQ_COUNT_A lock (source=off)': 0}
    obs_bad = [n for n, v in want.items() if obs.get(n) is None or int(obs[n], 16) != v]
    res['observability'] = dict(reads=obs, expected={k: f'{v:04x}' for k, v in want.items()}, mismatches=obs_bad)
    # 5. host-link loopback (D2H pins -> H2D pins), every host_link_mode: core status bit 9
    #    (frame receiver locked on the transport's own D2H training prefix) and bit 8 (rx fault)
    lb = dict(status='missing')
    try:
        lr, lg = parse(out / 'loopback/rtl/tb.log'), parse(out / 'loopback/gl/tb.log')
        modes = json.loads((out / 'loopback/expect.json').read_text())['modes']
        st = [r[2] for r in lg if r[0] == 'R' and r[1] == 0x03]
        per = {}
        for m, v in zip(modes, st):
            per[f'mode{m}'] = dict(status=v, locked=bool(int(v, 16) >> 9 & 1), rx_fault=bool(int(v, 16) >> 8 & 1))
        good = len(st) == len(modes) + 1 and all(p['locked'] and not p['rx_fault'] for p in per.values())
        lb = dict(status='pass' if good and lr == lg else 'fail', lockstep_equal=lr == lg, per_mode=per,
                  final_status_after_stop=st[-1] if st else None,
                  modes={'0': 'DDR', '1': 'SDR', '2': 'SDR reduced'})
    except (FileNotFoundError, ValueError) as e:
        lb['error'] = str(e)
    res['host_link_loopback'] = lb
    ok = not lock and not mm and not viol and not obs_bad and rs >= 4 and lb.get('status') == 'pass'
    res['status'] = 'pass' if ok else 'fail'
    (out / 'gls-report.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res, indent=1))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
