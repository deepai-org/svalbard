#!/usr/bin/env python3
"""Command stream for the macro-level gate-level simulation (sim/tb_digital_gl.sv).

The stream is exactly the register-file stimulus of verification/check_regfile.py (same seed
and random length as evidence/regfile-verification.json: reset defaults of all 256 addresses,
per-register sweep, every rule violated and satisfied, isolation/power-good/fault forcing,
break-before-make, commit while running, reset mid-transaction, seeded random phase), followed
by a directed observability section: ID/ABI/hash, POR and RESET_N cause flags, island status and
fault over SPI, and core status with the fast clocks running. Expectations from the reference
model are written next to the commands (expect.json) for gls_check.py.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

P = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('check_regfile', P / 'verification/check_regfile.py')
CR = importlib.util.module_from_spec(spec)
sys.modules['check_regfile'] = CR
spec.loader.exec_module(CR)


def build(seed, n_random):
    s, info = CR.build(seed, n_random)
    n_stream = len(s.cmds)
    # ---- directed observability section
    for a in (0x00, 0x08, 0x09):
        s.read(a)
    s.power_on_reset()            # POR alone (RESET_N pad high)
    s.read(0x0D)                  # b0 POR occurred, b1 reset occurred
    s.write(0x0D, 0x0003)         # W1C both flags
    s.read(0x0D)
    s.reset()                     # RESET_N pad alone
    s.read(0x0D)                  # reset flag only
    s.inputs(0x2A, 1)             # island power-good pattern and monitor fault
    s.read(0x0A)
    s.read(0x0B)
    s.inputs(0, 0)
    s.read(0x0A)
    s.read(0x0B)
    # analog status inputs (observable only on DBG_OBS; raw), then run the fast clocks with ENABLE=1
    s.cmds.append('8 fff 1fff 0')
    s.write(0x01, 0x0001)
    s.cmds.append('9 1 4 0')      # run all fast clocks (50 MHz) for 4 us
    s.read(0x03)                  # core status (lockstep only; model has a bench constant)
    s.snap()
    s.write(0x01, 0x0000)
    s.cmds.append('9 1 2 0')
    s.read(0x03)
    s.cmds.append('9 0 0 0')      # stop the clocks
    s.cmds.append('8 0 0 0')
    s.reset()
    s.snap()
    # frequency counter a (rtl/pt_freq_count.sv, P3-7): the bench drives every source with the reference
    # clock; source = tx_ring_fbck, window 256, target 256, 1 window, tolerance 2 -> locked, count 256;
    # then source = off clears it.
    F = CR.F
    enc = lambda n, v: F[n]['values'].index(v)
    s.set_fields({'debug.freq_count_a.source': enc('debug.freq_count_a.source', 'tx_ring_fbck'),
                  'debug.freq_count_a.window': enc('debug.freq_count_a.window', 256),
                  'debug.freq_count_a.count': enc('debug.freq_count_a.count', 1),
                  'debug.freq_count_a.target': 256})
    s.commit()
    s.cmds.append('9 1 16 0')     # 16 us of 50 MHz REF and FBCK: 3 windows of 256
    s.read(pll_lock_addr())
    s.read(pll_lock_addr() + 1)
    s.set_fields({'debug.freq_count_a.source': 0})
    s.commit()
    s.cmds.append('9 1 2 0')
    s.cmds.append('9 0 0 0')
    s.read(pll_lock_addr())
    return s, info, n_stream


def pll_lock_addr():
    """Address of status.freq_count_a {locked, lost_lock, diff} (count at +1) from the register-map model."""
    f = {sf['name']: sf for sf in CR.M.STATUS_FIELDS}
    a = {f[n]['addr'] for n in ('status.freq_count_a.locked', 'status.freq_count_a.lost_lock', 'status.freq_count_a.diff')}
    assert len(a) == 1 and f['status.freq_count_a.count']['addr'] == min(a) + 1, a
    return a.pop()


def pll_lock_layout():
    f = {sf['name']: sf for sf in CR.M.STATUS_FIELDS}
    return {k: f['status.freq_count_a.' + k]['reg_lsb'] for k in ('locked', 'lost_lock', 'diff')}


def build_loopback():
    """Host-link loopback (tb with PT_LOOPBACK): for each host_link_mode, stop, program
    mode + d2h_enable, commit, ENABLE=1, run the clocks, read core status (bit 9 locked,
    bit 8 rx_fault), then stop. Expectations are checked by gls_check.py."""
    m = CR.Model()
    s = CR.Stimulus(m)
    modes = []
    for mode in (0, 1, 2):
        s.write(0x01, 0x0000)
        s.cmds.append('9 1 1 0')           # ENABLE=0 must reach the word-clock domains: run 1 us
        # SDR forwarded clocks exist only at the reduced rates (rtl/pt_host_link.sv): SDR modes run at div2.
        s.set_fields({'hostio.controls.d2h_enable': 1, 'debug.host_link.mode': mode,
                      'debug.host_link.rate': 0 if mode == 0 else 1})
        s.commit()
        s.write(0x01, 0x0001)
        s.cmds.append('9 1 30 0')          # 30 us of 50 MHz word clock
        s.read(0x03)
        s.cmds.append('9 0 0 0')
        modes.append(mode)
    s.write(0x01, 0x0000)
    s.cmds.append('9 1 1 0')
    s.set_fields({'hostio.controls.d2h_enable': 0})
    s.commit()
    s.cmds.append('9 1 4 0')
    s.read(0x03)
    s.cmds.append('9 0 0 0')
    return s, modes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=20261108)
    ap.add_argument('--random', type=int, default=3000)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    s, info, n_stream = build(a.seed, a.random)
    (out / 'commands.txt').write_text('\n'.join(s.cmds) + '\n')
    reset_snapshot = CR.Model().snapshot(in_reset=True)
    exp = [list(e[:2]) + [list(e[2]) if isinstance(e[2], tuple) else e[2]] for e in s.expect]
    status_addrs = sorted(a for a in range(256) if CR.M.status_read(a, {}) is not None)
    (out / 'expect.json').write_text(json.dumps(dict(
        seed=a.seed, random_operations=a.random, commands=len(s.cmds), regfile_stream_commands=n_stream,
        reads=s.stats['reads'], snapshots=s.stats['snaps'] + 1, status_addrs=status_addrs,
        reset_snapshot=list(reset_snapshot), expect=exp, id=CR.M.ID_VALUE, abi=CR.M.ABI_VERSION,
        pll_lock_addr=pll_lock_addr(), pll_lock_lsb=pll_lock_layout(),
        map_hash=CR.M.MAP_HASH)) + '\n')
    print(f'{len(s.cmds)} commands ({n_stream} regfile stream), {s.stats["reads"]} reads, {s.stats["snaps"]} snapshots')
    lb, modes = build_loopback()
    (out / 'loopback').mkdir(exist_ok=True)
    (out / 'loopback/commands.txt').write_text('\n'.join(lb.cmds) + '\n')
    (out / 'loopback/expect.json').write_text(json.dumps(dict(modes=modes)) + '\n')


if __name__ == '__main__':
    main()
