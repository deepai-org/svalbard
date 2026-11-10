#!/usr/bin/env python3
"""Simulate the generated SPI register file (pt_mgmt) against its reference model.

Stimulus is generated here from the generated bench model rtl/gen/pt_regmap.py:
reset defaults of all 256 addresses (shadow and active views), a per-register
write/readback/out-of-range sweep, one violating and one satisfying commit per
rule, island isolation / power-good / override / fault forcing, break-before-make,
commit-while-running, reset in the middle of a transaction, and a seeded random
phase. sim/tb_regfile.sv executes it over the SPI pins under Icarus and Verilator;
every read and every output snapshot is compared with the model.

    python3 verification/check_regfile.py [--random N] [--seed S] [--sim iverilog|verilator|both]
"""
import argparse
import importlib.util
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

P = Path(__file__).resolve().parents[1]
ROOT = P.parents[1]
_spec = importlib.util.spec_from_file_location('pt_regmap', P / 'rtl/gen/pt_regmap.py')
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

STATUS, OBS, WSTAT, CAPTURE = 0xA5C3, 0x9E3779B9, 0x6A09, 0x5A1234
LEGACY_LOCKED = (0x02, 0x04, 0x10, 0x11, 0x12, 0x21, 0x22, 0x23)
F = M.FIELD_BY_NAME
NISL = len(M.ISLANDS)


def valid_codes(f, limit=64):
    if f['allowed'] is not None:
        return list(f['allowed'])
    lo, hi = f['minimum'], f['maximum']
    if hi - lo < limit:
        return list(range(lo, hi + 1))
    return sorted({lo, lo + 1, (lo + hi) // 2, hi - 1, hi})


class Model:
    """Cycle-free model of pt_regfile at SPI-transaction granularity."""

    def __init__(self):
        self.pgood = 0
        self.fault = 0
        self.status_inputs = {}
        self.reset()
        self.por_flag = self.rst_flag = 1   # bench starts with a power-on reset

    def reset(self, por=False):
        self.rst_flag = 1
        if por:
            self.por_flag = 1
        self.shadow = M.reset_config()
        self.active = M.reset_config()
        self.enable = self.mode8 = self.index = self.play_i = self.rejected = 0
        self.trims = {0x10: 0, 0x11: 0, 0x12: 0}
        self.pb = self.ce = self.view = self.last_ok = self.count = 0
        self.err_code = self.err_addr = self.cfg_err = self.toggle = 0

    def write(self, a, d):
        info = None
        if a == 0x01:
            self.enable = d & 1
        elif a == 0x20:
            self.index = d & 31
        elif a in LEGACY_LOCKED:
            if self.enable:
                self.rejected = 1
                self.cfg_err |= M.ERR_LEGACY_LOCKED
                self.err_addr = a
            elif a == 0x02:
                self.mode8 = d & 1
            elif a == 0x04:
                self.rejected = 0
            elif a in self.trims:
                self.trims[a] = d
            elif a == 0x21:
                self.play_i = d & 0xFFF
            elif a == 0x23:
                self.pb, self.ce = d & 1, (d >> 1) & 1
        elif a == 0x05:
            self.cfg_err &= ~d & 0x7F
        elif a == 0x0D:
            if d & M.RST_POR_OCCURRED:
                self.por_flag = 0
            if d & M.RST_RESET_OCCURRED:
                self.rst_flag = 0
        elif a == 0x06:
            if d == M.COMMIT_CMD:
                code = M.commit_code(self.shadow, self.active, self.enable)
                info = code
                if code == 0:
                    self.active = dict(self.shadow)
                    self.toggle ^= 1
                    self.count = (self.count + 1) & 0xFF
                    self.last_ok, self.err_code = 1, 0
                else:
                    self.last_ok, self.err_code = 0, code
                    self.cfg_err |= M.commit_error_bit(code)
            elif d == M.REVERT_CMD:
                self.shadow = dict(self.active)
            else:
                self.cfg_err |= M.ERR_WRITE_RANGE
                self.err_addr = a
        elif a == 0x07:
            if d >> 1 == 0:
                self.view = d & 1
            else:
                self.cfg_err |= M.ERR_WRITE_RANGE
                self.err_addr = a
        elif M.register_at(a):
            reg = M.register_at(a)
            if M.reg_write_ok(reg, d):
                M.reg_apply(reg, d, self.shadow)
            else:
                self.cfg_err |= M.ERR_WRITE_RANGE
                self.err_addr = a
        else:
            self.rejected = 1
            self.cfg_err |= M.ERR_ADDRESS
            self.err_addr = a
        return info

    def pending(self):
        return int(any(self.shadow[k] != self.active[k] for k in self.shadow))

    def read(self, a):
        on = M.outputs(self.active, self.pgood, self.fault)['island_on']
        fixed = {0x00: M.ID_VALUE, 0x01: self.enable, 0x02: self.mode8, 0x03: STATUS, 0x04: self.rejected,
                 0x05: self.cfg_err, 0x06: (self.count << 8) | (self.pending() << 2) | (self.last_ok << 1) | self.toggle,
                 0x07: self.view, 0x08: M.ABI_VERSION, 0x09: M.MAP_HASH, 0x0A: (self.pgood << 8) | on,
                 0x0B: self.fault, 0x0C: (self.err_code << 8) | self.err_addr, 0x0D: (self.rst_flag << 1) | self.por_flag,
                 0x10: self.trims[0x10], 0x11: self.trims[0x11], 0x12: self.trims[0x12], 0x20: self.index,
                 0x23: (self.ce << 1) | self.pb, 0x24: 0, 0x25: CAPTURE & 0xFFFF, 0x26: CAPTURE >> 16}
        if a in fixed:
            return fixed[a]
        st = M.status_read(a, self.status_inputs)
        if st is not None:
            return st
        reg = M.register_at(a)
        if reg:
            return M.reg_read(reg, self.active if self.view else self.shadow)
        return 0

    def snapshot(self, in_reset=False, mid=False):
        o = M.outputs(self.active, self.pgood, self.fault)
        v = o['fields']
        cs = F['debug.clk_select.rf_lo']['values']
        obs_src = F['debug.clk_obs.source']['values']
        wsrc = F['debug.wclk_obs.source']['values']
        clk = [n for n in v if n.startswith('debug.clk_select.')]
        dbg_on = (o['island_on'] >> M.ISLANDS['debug']) & 1
        aux = dbg_on and (any(v[n] == cs.index('aux_clk') for n in clk) or v['debug.clk_obs.source'] == obs_src.index('aux_clk'))
        wclk = dbg_on and (any(v[n] == cs.index('wclk_in') for n in clk) or v['debug.clk_obs.source'] == obs_src.index('wclk_in')
                or v['debug.wclk_obs.source'] == wsrc.index('wclk_in'))
        dsrc = [0, 0, 1, self.toggle] + [(OBS >> i) & 1 for i in range(32)] + [int(not in_reset)]
        wsrc_bits = [0, 0, 1] + [(WSTAT >> i) & 1 for i in range(16)]
        s0, s1, ws = v['debug.dbg_obs.sel0'], v['debug.dbg_obs.sel1'], v['debug.wdbg_obs.select']
        bits5 = f"{int(aux)}{int(wclk)}{int(bool(dbg_on and v['debug.wtx_ext.enable']))}{int(v['debug.clk_obs.source'] != 0)}{int(v['debug.wclk_obs.source'] != 0)}"
        bits6 = f"{dsrc[s0]}{int(s0 != 0)}{dsrc[s1]}{int(s1 != 0)}{wsrc_bits[ws]}{int(ws != 0)}"
        bits2 = f"{self.toggle}{int(self.cfg_err != 0)}"
        return (o['analog_cfg'], o['debug_cfg'], o['island_en'], o['island_on'], o['atb0_sw'], o['atb1_sw'],
                bits5, bits6, bits2, self.enable, self.mode8, (self.pb << 1) | self.ce, int(mid and not in_reset), 0,
                o['atb0_grp'], o['atb1_grp'], f"{int(o['atb0_sw'] != 0)}{int(o['atb1_sw'] != 0)}")


class Stimulus:
    def __init__(self, model):
        self.m = model
        self.cmds = []
        self.expect = []
        self.stats = dict(commits_accepted=0, commits_rejected=0, codes=set(), reads=0, snaps=0)

    def write(self, a, d):
        self.cmds.append(f'0 {a:02x} {d:04x} 0')
        code = self.m.write(a, d)
        if code is not None:
            self.stats['commits_accepted' if code == 0 else 'commits_rejected'] += 1
            self.stats['codes'].add(code)
        return code

    def read(self, a):
        self.cmds.append(f'1 {a:02x} 0 0')
        self.expect.append(('R', a, self.m.read(a)))
        self.stats['reads'] += 1

    def inputs(self, pgood, fault):
        self.m.pgood, self.m.fault = pgood, fault
        self.cmds.append(f'2 {pgood:02x} {fault:x} 0')

    def status(self, locked, lost, errors_gray):
        self.m.status_inputs = dict(pattern_locked=locked, pattern_lost_lock=lost, pattern_errors_gray=errors_gray)
        self.cmds.append(f'7 {locked | (lost << 1):x} {errors_gray:04x} 0')

    def snap(self):
        self.cmds.append('4 0 0 0')
        self.expect.append(('S', 'SNAP', self.m.snapshot()))
        self.stats['snaps'] += 1

    def reset(self):
        self.m.reset()
        self.cmds.append('3 0 0 0')
        self.expect.append(('S', 'RST', self.m.snapshot(in_reset=True)))
        self.stats['snaps'] += 1

    def power_on_reset(self):
        self.m.reset(por=True)
        self.cmds.append('6 0 0 0')
        self.expect.append(('S', 'POR', self.m.snapshot(in_reset=True)))
        self.stats['snaps'] += 1

    def reset_mid(self, a, d):
        self.m.reset()
        self.cmds.append(f'5 {a:02x} {d:04x} 0')
        self.expect.append(('S', 'MID', self.m.snapshot(in_reset=True, mid=True)))
        self.stats['snaps'] += 1

    def set_fields(self, values):
        """Write the registers holding these fields (other fields keep their shadow values)."""
        cfg = dict(self.m.shadow)
        cfg.update(values)
        touched = sorted({c['addr'] for n in values for c in F[n]['chunks']})
        for a in touched:
            self.write(a, M.reg_read(M.register_at(a), cfg))

    def commit(self):
        code = self.write(0x06, M.COMMIT_CMD)
        self.read(0x06)
        self.read(0x0C)
        self.read(0x05)
        self.write(0x05, 0x7F)
        return code


def satisfy(cond):
    name, op, vals = cond
    codes = valid_codes(F[name])
    if op in ('eq', 'in'):
        return vals[0]
    pick = [c for c in codes if c not in vals and c != 0] or [c for c in codes if c not in vals]
    return pick[0]


def violate(cond):
    name, op, vals = cond
    codes = valid_codes(F[name])
    if op in ('ne', 'nin'):
        return vals[0]
    pick = [c for c in codes if c not in vals and c != 0] or [c for c in codes if c not in vals]
    return pick[0]


def rule_configs(rule):
    trig = {}
    for c in rule['if_all']:
        trig[c[0]] = satisfy(c)
    if rule['if_any']:
        trig[rule['if_any'][0][0]] = satisfy(rule['if_any'][0])
    bad = dict(trig)
    bad[rule['then_all'][0][0]] = violate(rule['then_all'][0])
    good = dict(trig)
    for c in rule['then_all']:
        good[c[0]] = satisfy(c)
    return repair(bad, rule), repair(good, None)


def repair(values, target):
    """Satisfy every rule that fails ahead of target (all failing rules when target is None),
    without touching the fields that define the case."""
    fixed = set(values)
    values = dict(values)
    for _ in range(32):
        cfg = M.reset_config()
        cfg.update(values)
        failing = [r for r in M.RULES if not M.rule_ok(r, cfg) and r is not target]
        if target is not None:
            failing = [r for r in failing if M.RULES.index(r) < M.RULES.index(target)]
        if not failing:
            break
        changed = False
        for c in failing[0]['then_all']:
            if c[0] not in fixed and not M.cond_ok(c, cfg):
                values[c[0]] = satisfy(c)
                changed = True
        if not changed:
            break
    return values


def all_islands_on():
    return {f'debug.island_power.{i}': 1 for i in M.ISLANDS}


def build(seed, n_random):
    m = Model()
    s = Stimulus(m)
    rng = random.Random(seed)
    full = (1 << NISL) - 1
    # A. Reset defaults, every address, both views.
    s.snap()
    for a in range(256):
        s.read(a)
    s.write(0x07, 1)
    for reg in M.REGISTERS:
        s.read(reg['addr'])
    s.write(0x07, 0)
    # B. Per-register sweep: max codes, min codes, a rejected value, restore.
    swept = rejected_values = 0
    for reg in M.REGISTERS:
        hi = lo = 0
        bad = None
        for name, fl, w, rl in reg['chunks']:
            f = F[name]
            if f['split'] or f['store'] is None:   # dropped fields: any write is ignored
                hi |= ((1 << w) - 1) << rl
                continue
            codes = valid_codes(f, limit=1 << 16)
            hi |= max(codes) << rl
            lo |= min(codes) << rl
            if bad is None:
                for code in range(1 << w):
                    if not M.field_ok(f, code):
                        bad = (lo & ~(((1 << w) - 1) << rl)) | (code << rl)
                        break
        if bad is None and reg['writable_mask'] != 0xFFFF:
            bad = lo | (~reg['writable_mask'] & 0xFFFF & -(~reg['writable_mask'] & 0xFFFF))
        for value in (hi, lo):
            s.write(reg['addr'], value)
            s.read(reg['addr'])
        if bad is not None:
            s.write(reg['addr'], bad)
            s.read(reg['addr'])
            s.read(0x05)
            s.read(0x0C)
            s.write(0x05, 0x7F)
            rejected_values += 1
        s.write(reg['addr'], reg['reset'])
        swept += 1
    s.write(0x06, M.REVERT_CMD)
    s.read(0x06)
    for a in (0x0D, 0x0E, 0x0F, 0x30, 0x3F, 0x55, 0x5F, 0xE4, 0xF0, 0xFF, 0x00, 0x08, 0x09, 0x0A, 0x0B):
        s.write(a, 0x1234)
        s.read(0x04)
        s.read(0x05)
        s.read(0x0C)
        s.write(0x05, 0x7F)
        s.write(0x04, 0)
    # C. One violating and one satisfying commit per rule.
    rule_hits = []
    for idx, rule in enumerate(M.RULES):
        bad, good = rule_configs(rule)
        cfg = M.reset_config()
        cfg.update(bad)
        assert not M.rule_ok(rule, cfg), rule['id']
        s.reset()
        s.set_fields(bad)
        code = s.commit()
        rule_hits.append((rule['id'], code))
        s.write(0x06, M.REVERT_CMD)
        s.set_fields(good)
        if s.commit() == 0:
            s.set_fields(all_islands_on())
            s.commit()
            s.inputs(full, 0)
            s.snap()
            s.inputs(full, 1)
            s.snap()
            s.inputs(0, 0)
            s.snap()
    # D. Island isolation, power-good, override and fault forcing on a rich legal configuration.
    rich = {'lna.state.state': 1, 'rxmix_i.state.state': 2, 'rfdriver.state.state': 1, 'rfdriver.mute.mute': 0,
            'ctle.state.state': 1, 'cdr.state.state': 1, 'adc_i.state.state': 1, 'adc_i.config.enable': 1,
            'usbhs.state.state': 1, 'wiredtx.state.state': 2, 'wiredtx.idle.idle': 0, 'txpad.config.branch': 1,
            'debug.replica.ringosc_enable': 1, 'debug.clk_obs.source': F['debug.clk_obs.source']['values'].index('ring_osc'),
            'debug.clk_obs.divider_log2': 5, 'debug.wmon_select.select': 4, 'debug.atb.atb1': 14, 'debug.atb.atb0': 43,
            'debug.clk_select.rf_lo': 3, 'debug.clk_select.wire_sample': 4, 'debug.wclk_obs.source': 1,
            'debug.dbg_obs.sel0': 5, 'debug.dbg_obs.sel1': 3, 'debug.wdbg_obs.select': 7, 'bias.trim.code': 17,
            'debug.bb_tap.mode': 1, 'consolidation.pll.owner': 1, 'consolidation.pll.feedback_n': 2, 'rfpll.state.state': 1,
            'consolidation.bbfilter.direction': 1, 'consolidation.bbfilter.bw': 5, 'consolidation.bbfilter.gain': 9,
            'slicer.offset.data': 0xAB, 'rfdriver.gain.code': 0xD7, 'adc_i.config.decision_ns': 77,
            'monitor.config.qualification_ticks': 0x12345678,
            'usbhs.bias.code': 0x7F, 'usbhs.bias.enable': 1}
    s.reset()
    s.set_fields(rich)
    assert s.commit() == 0
    s.snap()
    s.set_fields(all_islands_on())
    assert s.commit() == 0
    for pgood, fault in ((0, 0), (full, 0), (0b010101, 0), (full, 1), (0, 1), (full, 0)):
        s.inputs(pgood, fault)
        s.snap()
        s.read(0x0A)
        s.read(0x0B)
    s.set_fields({f'debug.pgood_override.{i}': 1 for i in ('rf', 'pll', 'debug')})
    assert s.commit() == 0
    s.inputs(0, 0)
    s.snap()
    s.read(0x0A)
    # Core reference-chain force preconditions (analog/core_support/README.md).
    s.set_fields({'debug.atb.atb0': 0})
    assert s.commit() == 0
    s.set_fields({'core.refchain.bgap_ena': 1, 'core.biasgen.ena': 1})
    assert s.commit() == 0
    s.set_fields({'debug.atb.atb0': 55})                       # VBG force with the bandgap on
    assert s.commit() != 0
    s.write(0x06, M.REVERT_CMD)
    s.set_fields({'debug.atb.atb0': 1})                        # ROOT_REF force with idac2 running
    assert s.commit() != 0
    s.set_fields({'core.biasgen.idac2_source': 0})
    assert s.commit() == 0
    s.set_fields({'debug.atb.atb0': 0})
    assert s.commit() == 0
    s.set_fields({'core.refchain.dist_en_debug': 1, 'debug.atb.atb0': 56})   # TRK_DEBUG, island on
    assert s.commit() != 0
    s.set_fields({'debug.island_power.debug': 0})              # README idac2 trim: island off
    assert s.commit() == 0
    s.set_fields({'core.biasgen.ref_sel_fine': 1})             # fine-only range
    assert s.commit() != 0
    s.write(0x06, M.REVERT_CMD)
    s.set_fields({'core.biasgen.ref_sel_coarse': 1, 'core.biasgen.ref_sel_fine': 1, 'core.refchain.bgap_trim': 5})
    assert s.commit() == 0
    s.inputs(full, 0)
    s.snap()
    s.set_fields({'debug.atb.atb0': 0})
    assert s.commit() == 0
    s.set_fields({'debug.atb.atb0': 14})                       # TRK_RF force, trunk off: allowed
    assert s.commit() == 0
    s.set_fields({'debug.atb.atb0': 2})       # sense-only node on the force bus: write rejected
    s.read(0x05)
    s.read(F['debug.atb.atb0']['chunks'][0]['addr'])
    s.write(0x05, 0x7F)
    # E. Break-before-make.
    s.set_fields({'debug.atb.atb1': 15})
    assert s.commit() != 0
    s.set_fields({'debug.atb.atb1': 0})
    assert s.commit() == 0
    s.set_fields({'debug.atb.atb1': 15})
    assert s.commit() == 0
    s.set_fields({'debug.clk_select.rf_lo': 2})
    assert s.commit() != 0
    s.write(0x06, M.REVERT_CMD)
    s.snap()
    # F. Commit while running: only live fields may change.
    s.write(0x01, 1)
    s.write(0x10, 0x1234)
    s.read(0x10)
    s.read(0x05)
    s.write(0x05, 0x7F)
    s.set_fields({'debug.dbg_obs.sel0': 9, 'debug.island_power.conv': 0})
    assert s.commit() == M.CODE_RUNNING
    s.set_fields({'debug.island_power.conv': 1})
    assert s.commit() == 0
    s.snap()
    s.set_fields({'debug.atb.atb1': 0})
    assert s.commit() == 0
    s.write(0x07, 1)
    for a in sorted({c['addr'] for c in F['debug.dbg_obs.sel0']['chunks'] + F['debug.atb.atb1']['chunks']}):
        s.read(a)
    s.write(0x07, 0)
    s.write(0x01, 0)
    # F2. Reset-cause flags and the live reset level on DBG_OBS (code 36).
    s.read(0x0D)
    s.write(0x0D, 0x0003)
    s.read(0x0D)
    s.set_fields({'debug.dbg_obs.sel1': 36})
    assert s.commit() == 0
    s.snap()
    s.reset()                      # RESET_N only: rst_flag set, por_flag stays clear
    s.read(0x0D)
    s.write(0x0D, 0x0002)
    s.read(0x0D)
    s.power_on_reset()             # POR: both set
    s.read(0x0D)
    s.write(0x0D, 0x0001)
    s.read(0x0D)
    # F2b. Pattern injection: live while running, but only with a pattern mode committed.
    s.write(0x01, 1)
    s.set_fields({'debug.pattern.inject': 1})
    assert s.commit() == 1 + [r['id'] for r in M.RULES].index('pattern_inject_needs_mode')
    s.write(0x06, M.REVERT_CMD)
    s.set_fields({'debug.pattern.tx_mode': 1})
    assert s.commit() == M.CODE_RUNNING             # mode is not live
    s.write(0x06, M.REVERT_CMD)
    s.write(0x01, 0)
    s.set_fields({'debug.pattern.tx_mode': 1})
    assert s.commit() == 0
    s.write(0x01, 1)
    s.set_fields({'debug.pattern.inject': 1, 'debug.pattern.check_clear': 1})
    assert s.commit() == 0                          # live fields while running
    s.snap()
    s.set_fields({'debug.pattern.inject': 0, 'debug.pattern.check_clear': 0})
    assert s.commit() == 0
    s.write(0x01, 0)
    # F3. Read-only status: synchronized, Gray-decoded, writes rejected as address errors.
    st_addrs = sorted({sf['addr'] for sf in M.STATUS_FIELDS})
    for locked, lost, count in ((1, 0, 0), (1, 1, 1), (0, 1, 0x1234), (1, 0, 0xFFFF), (0, 0, 0x8000)):
        s.status(locked, lost, count ^ (count >> 1))
        for a in st_addrs:
            s.read(a)
    for a in st_addrs:
        s.write(a, 0xFFFF)
        s.read(0x05)
        s.read(0x0C)
        s.write(0x05, 0x7F)
    # G. Reset in the middle of a transaction while everything is on.
    s.reset_mid(0x40, 0x003F)
    s.snap()
    for a in (0x00, 0x05, 0x06, 0x40, 0x41):
        s.read(a)
    # H. Seeded random phase.
    addrs = [r['addr'] for r in M.REGISTERS]
    for _ in range(n_random):
        r = rng.random()
        if r < 0.30:
            reg = M.register_at(rng.choice(addrs))
            if rng.random() < 0.75:
                v = 0
                for name, fl, w, rl in reg['chunks']:
                    f = F[name]
                    code = rng.choice(valid_codes(f)) if not f['split'] else rng.getrandbits(w)
                    v |= ((code >> fl) & ((1 << w) - 1) if f['split'] else code) << rl
            else:
                v = rng.getrandbits(16)
            s.write(reg['addr'], v)
        elif r < 0.40:
            # Mutate the active configuration slightly so that commits are often accepted.
            cfg = dict(m.active)
            for name in rng.sample(list(F), 2):
                cfg[name] = rng.choice(valid_codes(F[name]))
            if rng.random() < 0.5:
                cfg.update({f'debug.island_power.{i}': rng.getrandbits(1) for i in M.ISLANDS})
            s.write(0x06, M.REVERT_CMD)
            s.set_fields({k: v for k, v in cfg.items() if v != m.shadow[k]})
            s.commit()
        elif r < 0.48:
            s.write(0x06, rng.choice([M.COMMIT_CMD, M.COMMIT_CMD, M.REVERT_CMD, rng.getrandbits(16)]))
        elif r < 0.68:
            s.read(rng.choice(addrs + list(range(0x00, 0x10)) + [rng.getrandbits(8)]))
        elif r < 0.74:
            s.inputs(rng.getrandbits(NISL), int(rng.random() < 0.3))
        elif r < 0.84:
            s.snap()
        elif r < 0.90:
            s.write(rng.choice([0x0D, 0x01, 0x05, 0x07, 0x02, 0x10, 0x20, 0x21, 0x23, 0x04]), rng.getrandbits(16) & rng.choice([1, 3, 0x7F, 0xFFFF]))
        elif r < 0.95:
            s.write(rng.getrandbits(8), rng.getrandbits(16))
        elif r < 0.98:
            s.write(0x07, rng.getrandbits(1))
        elif r < 0.985:
            s.reset()
        elif r < 0.99:
            s.power_on_reset()
        else:
            s.reset_mid(rng.choice(addrs), rng.getrandbits(16))
    s.snap()
    for a in range(256):
        s.read(a)
    return s, dict(registers_swept=swept, rejected_value_writes=rejected_values, rule_hits=rule_hits)


def run_sim(sim, out, files):
    out.mkdir(parents=True, exist_ok=True)
    inc = str(P / 'rtl')
    if sim == 'iverilog':
        subprocess.run(['iverilog', '-g2012', '-I', inc, '-o', str(out / 'tb.vvp')] + files, check=True)
        r = subprocess.run(['vvp', '-n', 'tb.vvp'], cwd=out, capture_output=True, text=True, check=True)
    else:
        subprocess.run(['verilator', '--binary', '--timing', '-Wno-fatal', '-Wno-lint', '-Wno-style', '-O1',
                        '-I' + inc, '--top-module', 'tb_regfile', '-Mdir', str(out / 'obj'), '-o', 'tb'] + files,
                       check=True, capture_output=True, text=True)
        r = subprocess.run([str(out / 'obj' / 'tb')], cwd=out, capture_output=True, text=True, check=True)
    return r.stdout


def compare(log_lines, expect):
    mismatches = []
    lines = [ln.split() for ln in log_lines if ln.strip()]
    if not lines or lines[0][0] != 'S' or lines[0][1] != 'R0':  # initial snapshot taken during power-on reset
        return ['missing initial reset snapshot'], 0
    # Initial snapshot is taken during power-on reset: compare to the reset model.
    m0 = Model()
    exp_all = [('S', 'R0', m0.snapshot(in_reset=True))] + expect
    body = [ln for ln in lines if ln[0] in ('S', 'R')]
    if lines[-1][0] != 'E':
        mismatches.append('log not terminated')
    if len(body) != len(exp_all):
        mismatches.append(f'log has {len(body)} records, expected {len(exp_all)}')
    checked = 0
    for got, exp in zip(body, exp_all):
        if exp[0] == 'R':
            if got[0] != 'R' or any(ch in 'xXzZ' for ch in got[2]) or int(got[1], 16) != exp[1] or int(got[2], 16) != exp[2]:
                mismatches.append(f'read 0x{exp[1]:02X}: got {got[1:]} expected 0x{exp[2]:04X}')
        elif got[0] != 'S' or any(ch in 'xXzZ' for tok in got[2:] for ch in tok):
            mismatches.append(f'snapshot {exp[1]}: unknown or misplaced record {" ".join(got)[:120]}')
        else:
            vals = (int(got[2], 16), int(got[3], 16), int(got[4], 16), int(got[5], 16), int(got[6], 16), int(got[7], 16),
                    got[8], got[9], got[10], int(got[11], 16), int(got[12], 16), int(got[13], 16), int(got[14], 16), int(got[15], 16),
                    int(got[16], 16), int(got[17], 16), got[18])
            if got[1] != exp[1] or vals != exp[2]:
                names = ['analog_cfg', 'debug_cfg', 'island_en', 'island_on', 'atb0', 'atb1', 'rx/oe', 'obs', 'toggle/err',
                         'enable', 'mode8', 'pb/ce', 'miso_oe', 'miso', 'atb0_grp', 'atb1_grp', 'atb_en']
                diff = [n for n, g, e in zip(names, vals, exp[2]) if g != e]
                mismatches.append(f'snapshot {exp[1]} differs in {diff}')
        checked += 1
        if len(mismatches) > 20:
            break
    return mismatches, checked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--random', type=int, default=3000)
    ap.add_argument('--seed', type=int, default=20261108)
    ap.add_argument('--sim', choices=['iverilog', 'verilator', 'both'], default='both')
    ap.add_argument('--out', default=str(ROOT / 'scratch/pt_regfile/sim'))
    ap.add_argument('--rtl', default=str(P / 'rtl/pt_regfile.sv'), help='register file under test (mutation checks)')
    args = ap.parse_args()
    stim, info = build(args.seed, args.random)
    out = Path(args.out).resolve()
    files = [str(P / 'sim/tb_regfile.sv'), str(P / 'rtl/pt_spi.sv'), args.rtl]
    sims = ['iverilog', 'verilator'] if args.sim == 'both' else [args.sim]
    report = dict(seed=args.seed, random_operations=args.random, commands=len(stim.cmds),
                  reads_checked=stim.stats['reads'], snapshots_checked=stim.stats['snaps'],
                  commits_accepted=stim.stats['commits_accepted'], commits_rejected=stim.stats['commits_rejected'],
                  registers=len(M.REGISTERS), fields=len(M.FIELDS), rules=len(M.RULES), **{k: v for k, v in info.items() if k != 'rule_hits'})
    rule_codes = {code for _, code in info['rule_hits']}
    report['directed_rule_violations_rejected'] = sum(1 for _, code in info['rule_hits'] if code)
    report['rule_codes_exercised'] = sorted(c for c in stim.stats['codes'] if 0 < c < 0x80)
    report['all_rule_codes_exercised'] = all((i + 1) in stim.stats['codes'] for i in range(len(M.RULES)))
    ok = report['all_rule_codes_exercised'] and report['directed_rule_violations_rejected'] == len(M.RULES)
    for sim in sims:
        d = out / sim
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        (d / 'commands.txt').write_text('\n'.join(stim.cmds) + '\n')
        try:
            stdout = run_sim(sim, d, files)
        except subprocess.CalledProcessError as e:
            report[sim] = dict(status='error', detail=(e.stderr or '')[-2000:])
            ok = False
            continue
        mism, checked = compare((d / 'tb.log').read_text().splitlines(), stim.expect)
        report[sim] = dict(status='pass' if not mism else 'fail', records_checked=checked, mismatches=mism[:20],
                           stdout=stdout.strip().splitlines()[-1:] if stdout else [])
        ok = ok and not mism
    # Legacy pt_control equivalence (lockstep, random legacy-address transactions).
    leg = out / 'legacy'
    leg.mkdir(parents=True, exist_ok=True)
    subprocess.run(['iverilog', '-g2012', '-I', str(P / 'rtl'), '-o', str(leg / 'tb.vvp'), str(P / 'sim/tb_regfile_legacy.sv'),
                    str(P / 'rtl/pt_spi.sv'), str(P / 'sim/reference/pt_control.sv'), args.rtl], check=True)
    lines = subprocess.run(['vvp', '-n', str(leg / 'tb.vvp')], capture_output=True, text=True, check=True).stdout.splitlines()
    report['legacy_equivalence'] = [ln for ln in lines if ln.startswith('legacy') or ln in ('PASS', 'FAIL')]
    ok = ok and 'PASS' in lines
    # Chip integration: the top elaborates with every RTL file and exposes all 19 debug sites.
    readiness = json.loads((P / 'spec/tapeout-readiness.json').read_text())
    chip = (P / 'integration/pt_chip.sv').read_text()
    header = chip[chip.index('module pt_chip('):chip.index(');', chip.index('module pt_chip('))]
    missing = [d['name'] for d in readiness['debug_sites'] if d['name'] not in header.replace(',', ' ').split()]
    rtl = sorted(str(x) for x in (P / 'rtl').glob('*.sv'))
    elab = subprocess.run(['iverilog', '-g2012', '-I', str(P / 'rtl'), '-s', 'pt_chip', '-o', str(out / 'chip.vvp'),
                           str(P / 'integration/pt_chip.sv')] + rtl, capture_output=True, text=True)
    report['chip_integration'] = dict(debug_sites=len(readiness['debug_sites']), missing_debug_ports=missing,
                                      elaborates=elab.returncode == 0, elaboration_errors=elab.stderr[-1000:])
    ok = ok and not missing and elab.returncode == 0
    report['status'] = 'pass' if ok else 'fail'
    print(json.dumps(report, indent=1))
    (out / 'report.json').write_text(json.dumps(report, indent=1) + '\n')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
