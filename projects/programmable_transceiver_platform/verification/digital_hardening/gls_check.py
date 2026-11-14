#!/usr/bin/env python3
"""Check the macro-level gate-level simulation (gls.sh output).

1. Lockstep: the post-route netlist log equals the RTL macro log record by record (every SPI
   read, every snapshot of every macro output), X/Z included.
2. Reference model: every SPI read and every regfile-visible snapshot field of the netlist
   equals the generated register-map model (verification/check_regfile.py), except reads whose
   model value is a bench constant of tb_regfile (legacy STATUS 0x03, capture data 0x25/0x26,
   checker status registers) and the raw observation-mux values (those are covered by 1).
3. Reset safety: in every snapshot taken while reset is asserted (initial RESET_N+POR, RESET_N
   alone, POR alone, RESET_N in the middle of a write) no macro output is X/Z and every analog enable,
   pad driver enable and data bus of the SAFE0 list is 0 (the data buses are ANDed with their island).
4. Observability: directed SPI reads of ID/ABI/map hash, reset-cause flags (POR vs RESET_N),
   island power-good and fault status.
"""
import argparse
import hashlib
import json
from pathlib import Path

# r7: a snapshot is one "name=hex" token per macro output (sim/tb_digital_gl.sv + gls_ports.py), so the records follow
# the macro boundary. analog_cfg / debug_cfg are no longer macro ports: the register-file contents are checked through
# the SPI reads (model) and through every decoded c_* output (lockstep against the RTL macro).
# Outputs that must be 0 in every snapshot taken while a reset is asserted (analog enables, pad drivers, data buses).
SAFE0 = ['island_en', 'island_on', 'atb0_sw', 'atb1_sw', 'atb0_en', 'atb1_en', 'd2h_oe', 'd2h_clk_pin', 'clk_obs_oe',
         'dbg_obs0_oe', 'dbg_obs1_oe', 'rx_en_aux', 'rx_en_wclk', 'rx_en_wtx_ext', 'wire_rx_ptrim_en',
         'c_txpad_req_main', 'c_txpad_req_post', 'c_txpad_req_detect', 'c_txpad_req_term', 'c_wiredtx_ser_en',
         'c_wiredtx_bias_en', 'c_usb_tx_oe', 'c_usb_hs_drv', 'c_usb_hs_en', 'c_usb_fs_en', 'c_rfdriver_en',
         'c_pll_tx_en', 'c_pll_cdr_en', 'c_cdr_en', 'c_qvco_en', 'c_lo_mmd_en', 'c_lo_pfdcp_en', 'c_lna_en',
         'c_rxmix_i_en', 'c_rxmix_q_en', 'c_txmix_i_en', 'c_txmix_q_en', 'c_txsum_en', 'c_adc_i_en', 'c_adc_q_en',
         'c_dac_i_en', 'c_dac_q_en', 'c_slicer_en', 'c_wrx_cap_en', 'c_ctle_en', 'c_detect_en', 'c_term_en',
         'c_aosc_en', 'c_bias_dist_en_rf', 'c_bias_dist_en_conv', 'c_bias_dist_en_pll', 'c_bias_dist_en_wire',
         'c_bias_dist_en_debug', 'c_biasgen_ref_sel_vbg', 'c_cdr_fup', 'c_cdr_fdn', 'wire_tx_data', 'rf_tx_sample',
         'd2h_pin', 'spi_miso']


def parse(path):
    recs = []
    for ln in Path(path).read_text().splitlines():
        t = ln.split()
        if not t:
            continue
        if t[0] == 'S':
            recs.append(('S', t[1], dict(x.split('=', 1) for x in t[2:])))
        elif t[0] == 'R':
            recs.append(('R', int(t[1], 16), t[2]))
        elif t[0] == 'E':
            recs.append(('E', int(t[1])))
    return recs


def isx(v):
    return any(ch in 'xXzZ' for ch in v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out)
    exp = json.loads((out / 'expect.json').read_text())
    res = dict(status='fail')
    project = Path(__file__).resolve().parents[2]
    manifest = out / 'sources.sha256'
    hashes = {}
    stale = []
    if manifest.exists():
        for line in manifest.read_text().splitlines():
            digest, name = line.split(maxsplit=1)
            assert name.startswith('/src/'), name
            name = name.removeprefix('/src/')
            hashes[name] = 'sha256:'+digest
            path = project / name
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                stale.append(name)
    else:
        stale.append('missing simulation source manifest')
    res.update(source_hashes=hashes, stale_sources=stale)
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
            # ISLAND_STATUS (0x0A) b11 = power-good of the reserved island 3: no switch, tied 0 at the macro boundary
            want_rd = e[2] & ~0x0800 if e[1] == 0x0A else e[2]
            if any(ch in 'xXzZ' for ch in got[2]) or int(got[2], 16) != want_rd:
                mm.append(f'read 0x{e[1]:02X}: got {got[2]} expected 0x{want_rd:04X}')
        else:
            if got[0] != 'S' or got[1] != e[1]:
                mm.append(f'record order at snapshot {e[1]}: {got[:2]}')
                continue
            n_snaps += 1
            o, m = got[2], e[2]
            # model tuple (check_regfile.Model.snapshot): 2 island_en, 3 island_on, 4 atb0_sw, 5 atb1_sw, 7 dbg_obs
            # {obs0, oe0, obs1, oe1}, 14 atb0_grp, 15 atb1_grp. island bit 3 has no switch at macro level.
            keys = ('island_en', 'island_on', 'atb0_sw', 'atb1_sw', 'atb0_grp', 'atb1_grp', 'dbg_obs0_oe', 'dbg_obs1_oe')
            if any(isx(o[k]) for k in keys):
                mm.append(f'snapshot {e[1]}: X/Z in regfile-driven outputs')
                continue
            g = {k: int(o[k], 16) for k in keys}
            w = dict(island_en=m[2], island_on=m[3] & ~8, atb0_sw=m[4], atb1_sw=m[5], atb0_grp=m[14], atb1_grp=m[15],
                     dbg_obs0_oe=int(m[7][1]), dbg_obs1_oe=int(m[7][3]))
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
        o = r[2]
        for k in SAFE0:
            if k == 'spi_miso' and r[1] == 'MID':
                continue
            if k not in o:
                viol.append(f'{r[1]}: output {k} missing from the record')
            elif isx(o[k]) or int(o[k], 16) != 0:
                viol.append(f'{r[1]}: {k}={o[k]} (safe 0)')
        if r[1] != 'MID' and o.get('spi_miso_oe') != '0':
            viol.append(f'{r[1]}: miso_oe with CS_N high')
        if o.get('island_off') is None or isx(o['island_off']) or int(o['island_off'], 16) != 0x3f:
            viol.append(f'{r[1]}: island_off={o.get("island_off")} (safe 3f)')
        for k, v in o.items():
            if isx(v):
                viol.append(f'{r[1]}: {k} X/Z')
    res['reset_safety'] = dict(reset_snapshots=rs, violations=len(viol), first=viol[:10], outputs_checked_zero=SAFE0,
                               rule='no X/Z on any macro output; the listed enables, pad drivers and data buses 0; '
                                    'island_off all 1; MISO_OE 0 with CS_N high')
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
            'RESET_STATUS after W1C': 0, 'RESET_STATUS after RESET_N': 2, 'ISLAND_STATUS pgood=0x2A': 0x2200,  # bit 3 (reserved island) has no switch
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
    ok = bool(hashes) and not stale and not lock and not mm and not viol and not obs_bad and rs >= 4 and lb.get('status') == 'pass'
    res['status'] = 'pass' if ok else 'fail'
    (out / 'gls-report.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res, indent=1))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
