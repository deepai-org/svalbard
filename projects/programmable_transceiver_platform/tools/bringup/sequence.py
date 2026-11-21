"""Reference bring-up sequence, spec/bring-up.md sections 1-6 (steps cite the section). Board-independent: needs an
`spi` (xfer) and a `board` with reset(low: bool), wait_us(t) and optionally clk_obs_hz(). Returns a dict of findings;
raises on a failure that stops bring-up."""
import atb
from regs import Regs, FIELDS, STATUS, CommitError, ID, ABI, HASH, CHIP_ID, A_ID, A_ABI, A_HASH, A_ISLAND, A_FAULT, A_RESET, A_CFGERR

RING_TT_330 = 210.5e6           # bring-up.md section 6 (extracted pt_ring_osc, tt, 3.30 V, 27 C)
DIG_TT_330 = 101.5e6            # pt_dig_ring (41 mcu7t5v0 inversions) tt 3.30 V, schematic estimate (bring-up.md 6)
SWITCH_PG = {'rf': (0, 1, 2, 3), 'wired': (4, 5, 6), 'pll': (7,), 'conv': (8,), 'debug': (9,)}   # status.health.switch_pg
HALVED = (3, 7)                 # counter sources counted through a /2 flop (OBS-IMPL-1/2): count = edges / 2
ISLAND_BIT = {'wired': 0, 'rf': 1, 'pll': 2, 'conv': 4, 'debug': 5}
PAYLOAD = {'rf': ('rf', 'conv'), 'wired': ('wired',)}


EXTRA_ATB = ()          # negative control hook: a code with no leaf on this chip must read 'open bus'
RAIL_CODE = {'debug': 12, 'pll': 9, 'rf': 8, 'conv': 11, 'wired': 7}


def atb_walk(r, board, codes, vdd=3.30, log=print):
    """Sense each ATB1 code (zero code between two codes: break-before-make) and judge it against atb.EXPECT."""
    fails = []
    if not hasattr(board, 'atb_read'):
        log('  (no ATB meter on this board: skipped)'); return fails
    for c in codes:
        r.set(**{'debug.atb.atb1': 0}); r.commit()
        r.set(**{'debug.atb.atb1': c})
        if r.read(A_CFGERR) & 1:                 # write rejected: no leaf for this code on this chip (OBS-IMPL-3)
            r.write_reg(A_CFGERR, 0x7F); r.set(**{'debug.atb.atb1': 0})
            log(f'  ATB1 {c:2d} rejected by the register file (no leaf on pt_{r.chip})  FAIL'); fails.append(c); continue
        r.commit()
        v = board.atb_read(c); ion = r.read(A_ISLAND) & 0x3F
        ok, lim = atb.judge(c, v, vdd, ion)
        log(f'  ATB1 {c:2d} = {"open bus" if v is None else f"{v:.4f} V"}  [{lim}] {"ok" if ok else "FAIL"}')
        if not ok: fails.append(c)
    r.set(**{'debug.atb.atb1': 0}); r.commit()
    return fails


def trim_choice(s, s_dig=None):
    """Supply setpoint from the speed indices measured at 3.30 V (section 6): S = f_ring_osc / 210.5 MHz (3.3 V devices),
    S_dig = f_dig_ring / f_dig_ring(tt) (5 V-device macro cells). Slow if either is slow; fast only if both are fast."""
    slow = s < 0.91 or (s_dig is not None and s_dig < 0.86)
    fast = s > 1.09 and (s_dig is None or s_dig > 1.16)
    return 3.50 if slow else 3.20 if fast else 3.30


def run(spi, board, chip, f_ref, log=print):
    r, out = Regs(spi, chip), {}
    board.shadow = r.shadow          # later steps continue from the same host shadow
    # 1. power-up and reset (B49, B53): RESET_N low through the ramp, then release
    board.reset(True); board.wait_us(1000); board.reset(False); board.wait_us(10)
    rs = r.read(A_RESET); out['reset_status'] = rs
    log(f'1 RESET_STATUS 0x{rs:04X} (b0 POR seen, b2 strap)')
    # 2. identity (section 2)
    for name, addr, want in (('ID', A_ID, ID), ('ABI', A_ABI, ABI), ('MAP_HASH', A_HASH, HASH)):
        got = r.read(addr)
        if got != want:
            raise RuntimeError(f'2 {name} 0x{got:04X} != 0x{want:04X}')
    cid = r.status('status.chip.id')
    if cid != CHIP_ID[chip]:
        raise RuntimeError(f'2 chip id {cid}, expected {CHIP_ID[chip]} (pt_{chip})')
    isl = r.read(A_ISLAND)
    if isl:
        raise RuntimeError(f'2 ISLAND_STATUS 0x{isl:04X} with every island off: back-drive signature')
    log(f'2 ID/ABI/hash ok, chip id {cid}, islands 0, fault {r.read(A_FAULT)}, cfg_err {r.read(A_CFGERR)}')
    # 3. always-on observation: aosc, REF_IN, counter on aosc
    r.set(**{'core.aosc.enable': 1, 'refinput.state.state': 2, 'debug.dbg_obs.sel0': 35})
    r.commit()
    out['aosc_hz'] = count(r, board, 5, f_ref)
    log(f'3 aosc {out["aosc_hz"]/1e6:.2f} MHz via freq_count_a (ref {f_ref/1e6:g} MHz)')
    # 4. bias (B54): enables, >= 100 us AND >= 256 SCLK, then the reference selects
    r.set(**{'core.biasgen.ena': 1, 'core.refchain.bgap_ena': 1}); r.commit()
    board.wait_us(100); r.clocks(9)
    r.set(**{'core.biasgen.ref_sel_vbg': 1, 'core.biasgen.ref_sel_coarse': 1}); r.commit()
    log('4 bias on (256-SCLK interlock clocked); ATB1 walk:')
    out['atb_fail'] = atb_walk(r, board, (55, 1, 2, 3, 5, 13) + EXTRA_ATB, log=log)
    # 5. islands one at a time: debug, pll, payload groups; effective-on and pgood both set
    want = 0
    for isl_name in ('debug', 'pll') + PAYLOAD[chip]:
        r.set(**{f'debug.island_power.{isl_name}': 1}); r.commit(); board.wait_us(20)
        b = ISLAND_BIT[isl_name]; want |= (1 << b) | (1 << (b + 8))
        got = r.read(A_ISLAND)
        if got != want:
            raise RuntimeError(f'5 island {isl_name}: ISLAND_STATUS 0x{got:04X} != 0x{want:04X}')
        pg = r.status('status.health.switch_pg')
        bad = [b for b in SWITCH_PG[isl_name] if not pg >> b & 1 and not (chip == 'rf' and b in (4, 5, 6)) and not (chip == 'wired' and b in (0, 1, 2, 3, 8))]
        if bad:
            raise RuntimeError(f'5 island {isl_name}: switch power-good bits {bad} low (status.health.switch_pg 0x{pg:03X}): a dead switch in the group')
        log(f'5 island {isl_name} on, ISLAND_STATUS 0x{got:04X}, switch_pg 0x{pg:03X} (record the supply-current step)')
        rails = [RAIL_CODE[isl_name]] + ([10] if isl_name == 'wired' else [])
        out['atb_fail'] += atb_walk(r, board, rails, log=log)
    # 6. speed indicator: ring_osc on the counter (cross-check path; CLK_OBS is primary, OBS-2)
    r.set(**{'debug.replica.ringosc_enable': 1, 'debug.clk_obs.source': 10, 'debug.clk_obs.divider_log2': 2}); r.commit()
    f_ring = count(r, board, 3, f_ref)
    if hasattr(board, 'clk_obs_hz'):
        f_ring = 4 * board.clk_obs_hz()
    r.set(**{'debug.replica.dig_ring_enable': 1}); r.commit()
    f_dig = count(r, board, 7, f_ref)
    r.set(**{'debug.replica.dig_ring_enable': 0, 'debug.freq_count_a.source': 0}); r.commit()
    s, sd = f_ring / RING_TT_330, f_dig / DIG_TT_330
    out.update(ring_hz=f_ring, dig_ring_hz=f_dig, speed_index=s, dig_speed_index=sd, supply_setpoint=trim_choice(s, sd))
    log(f'6 ring_osc {f_ring/1e6:.1f} MHz (S {s:.3f}), dig_ring {f_dig/1e6:.1f} MHz (S_dig {sd:.3f}) -> supply setpoint {out["supply_setpoint"]:.2f} V')
    return out


def count(r, board, source, f_ref, window_code=1):
    """Frequency counter a on `source`; returns the source frequency from the last window count."""
    window = (256, 1024, 2048, 4096)[window_code]
    r.set(**{'debug.freq_count_a.source': 0}); r.commit()
    r.set(**{'debug.freq_count_a.source': source, 'debug.freq_count_a.window': window_code}); r.commit()
    board.wait_us(3.2 * window / f_ref * 1e6)        # first window only sets the reference point
    n = r.status('status.freq_count_a.count')
    return n * f_ref / window * (2 if source in HALVED else 1)


HOST_PRESCALE = 2      # /4. Host follow on the TX ring (D-HF): ring = f(H2D_CLK) x 4 (modulus code 2), word clock = ring / 4 = f(H2D_CLK)
PREFIX = [0x3A5, 0x05A, 0x2D3, 0x12C, 0x369, 0x096, 0x21E, 0x1E1]   # fpga-connection-plan.md section 1


def host_link(spi, fpga, chip, log=print, rate=2):
    """bring-up.md section 7: TX-ring host_follow clock (D-HF), div4, slow slew + stagger, then per-step link restarts
    while the FPGA sweeps its capture delay (FPGA-1: the prefix is sent once per link start); returns the window."""
    r = Regs(spi, chip)
    r.shadow = getattr(fpga, 'shadow', r.shadow)
    r.set(**{'clockmux.config.ring_ref': 3, 'ring_l.config.modulus': 2, 'ring_l.config.enable': 1,
             'clockmux.config.host_prescale': HOST_PRESCALE, 'debug.clk_select.host_clk': 1})
    r.commit()
    r.set(**{'debug.host_link.rate': rate, 'hostio.controls.slew': 1, 'hostio.controls.d2h_stagger': 1,
             'hostio.controls.d2h_enable': 1})
    r.commit()
    word_ns = 3.2 * (1, 2, 4)[rate]
    ok = []
    for step in range(16):
        # a link start = payload ENABLE (0x01 b0) 0 -> 1: the transport core leaves reset and the framer sends the
        # training quads T0, T1 once (pt_core crst, pt_quad_link_tx); the FPGA re-arms at the next tap first (FPGA-1)
        d = step * word_ns / 16
        r.write_reg(0x01, 0)
        fpga.arm(d * 1000)
        r.write_reg(0x01, 1)
        board_wait = getattr(fpga, 'wait_us', None)
        if board_wait: board_wait(1)
        words = fpga.captured()
        if getattr(fpga, 'trace', False) and step in (0, 1, 8): print('   probe', step, fpga._cmd('P 0 0 0').strip(), [hex(w) if w is not None else w for w in words[:20]])
        hit = any(words[i:i+8] == PREFIX for i in range(len(words) - 7))
        ok.append(hit)
    r.write_reg(0x01, 0)
    good = [i for i, h in enumerate(ok) if h]
    if not good:
        raise RuntimeError(f'7 no capture delay sees the training prefix ({"".join("x" if h else "." for h in ok)})')
    centre = good[len(good) // 2] * word_ns / 16
    log(f'7 host link div{(1,2,4)[rate]}: prefix seen at delays {"".join("x" if h else "." for h in ok)} (step {word_ns/16:.2f} ns), centre {centre:.2f} ns')
    return dict(window=ok, centre_ns=centre)


# Per-mode enable sequences (bring-up.md section 9). Step kinds: dict = set + commit (must be accepted);
# ('reject', dict) = a commit the register file must refuse (the dict is then reverted in the shadow);
# ('wait', us); ('status', name, want or None) = read a status field (None: log only). Third item: True = return
# the previous modes' fields to reset first; False = build on them.
# Order and values follow integration/chips/sim/tb_top_modes.sv sections 2-7, which check the analog pins.
MODES = {
    'rf': [
        ('rf receive, external LO (die-1 baseline)', [
            {'rfpll.config.lo_mode': 3},
            {'core.refchain.dist_en_rf': 1, 'core.refchain.dist_en_conv': 1},
            {'debug.clk_select.wire_line': 1, 'debug.clk_select.conv_sample': 1, 'clockmux.config.conv_prescale': 2},
            {'lna.state.state': 2, 'rxmix_i.state.state': 2, 'rxmix_q.state.state': 2, 'consolidation.bbfilter.direction': 1,
             'adc_i.state.state': 2, 'adc_q.state.state': 2, 'refbuf.state.state': 2, 'adc.config.interleave': 1}], False),
        ('rf transmit / duplex (on top of receive)', [
            ('reject', {'txmix_i.state.state': 2, 'txmix_q.state.state': 2, 'txsum.state.state': 2, 'rfdriver.state.state': 2,
                        'dac_i.state.state': 2, 'dac_q.state.state': 2}),      # RC-16k: TX with the LNA at full bias
            {'lna.bias.lo': 1, 'txmix_i.state.state': 2, 'txmix_q.state.state': 2, 'txsum.state.state': 2,
             'rfdriver.state.state': 2, 'dac_i.state.state': 2, 'dac_q.state.state': 2},
            {'rfdriver.mute.mute': 0, 'dac_i.config.hold_zero': 0, 'dac_q.config.hold_zero': 0}], False),
        ('on-chip LO synthesizer (analog/timing/README.md (LO integration) LO.4.2)', [
            {'core.refchain.dist_en_rf': 1},
            {'rfpll.config.lo_mode': 2, 'rfpll.state.state': 2, 'rfpll.config.lo_n': 24, 'rfpll.config.vco_coarse': 9,
             'rfpll.config.lo_icp': 3, 'rfpll.config.lo_preset': 1},
            ('reject', {'rfpll.config.lo_n': 10}),                               # lo_n < 16 with the synthesizer active
            ('wait', 20), {'rfpll.config.lo_preset': 0}], True),
    ],
    'wired': [
        ('wired transmit, serial x4', [
            {'core.refchain.dist_en_wire': 1},
            {'ring_l.config.lock_time': 3, 'ring_l.config.modulus': 1, 'txpad.config.branch': 1, 'wiredtx.idle.idle': 0,
             'consolidation.wiredtx_stage.rate_mode': 2, 'wiredtx.state.state': 2},
            {'ring_l.config.enable': 1}, ('wait', 700),
            ('status', 'status.wired.tx_state', 3), ('status', 'status.wired.tx_ring_ready', 1)], True),
        ('wired receive (CDR, CTLE, slicer, capture)', [
            {'core.refchain.dist_en_wire': 1, 'ring_l.config.modulus': 1, 'ring_l.config.enable': 1},
            {'cdr.state.state': 2},
            {'ctle.state.state': 2, 'slicer.state.state': 2, 'termination.config.hs_enable': 1,
             'termination.config.hs_term_enable': 1, 'ctle.config.peak': 5, 'ring_c.config.modulus': 3, 'ring_c.config.kp': 6,
             'slicer.capture.rate_mode': 1},
            ('wait', 100), ('status', 'status.wired.rx_state', None)], True),
        ('USB full speed, forced J (direct stream)', [
            {'core.refchain.dist_en_wire': 1, 'ring_l.config.modulus': 1, 'ring_l.config.enable': 1},
            {'usbdrive.select.branch': 2, 'usbdrive.state.state': 2, 'usbfs.config.drive_enable': 1,
             'usb.config.force_symbol': 1, 'usb.config.force_enable': 1, 'usbfs.config.pullup_p': 1},
            {'wiredtx.state.state': 2}, ('wait', 400),
            ('reject', {'usbhs.config.tx_enable': 1}),                           # HS and FS drive together
            ('status', 'status.usb.line', None)], True),
    ],
}


def _teardown(r, touched):
    """Return every field a mode touched to its reset value (one commit; reset codes are 0 / off, so no
    break-before-make conflict), keeping islands and bias trunks."""
    keep = ('core.refchain.', 'debug.island_power', 'core.', 'refinput.', 'debug.clk_select.host_clk', 'clockmux.config.ring_ref')
    back = {n: FIELDS[n]['default'] for n in touched if not n.startswith(keep)}
    if back:
        r.set(**back); r.commit()


def mode(spi, board, chip, log=print):
    """bring-up.md section 9: every mode of the chip in turn; each commit checked, expected rejections checked."""
    r = Regs(spi, chip)
    r.shadow = getattr(board, 'shadow', r.shadow)
    if chip == 'wired':      # the wired modes clock the TX ring from REF_IN (ring_ref = ref), not from H2D_CLK
        r.set(**{'hostio.controls.d2h_enable': 0, 'ring_l.config.enable': 0}); r.commit()
        r.set(**{'clockmux.config.ring_ref': 0}); r.commit()      # break-before-make: through 0
        r.set(**{'clockmux.config.ring_ref': 1}); r.commit()
    fails, touched = [], set()
    for name, steps, teardown_before in MODES[chip]:
        if teardown_before:
            _teardown(r, touched); touched = set()
        for st in steps:
            if isinstance(st, dict):
                r.set(**st); r.commit(); touched.update(st)
            elif st[0] == 'wait':
                board.wait_us(st[1])
            elif st[0] == 'reject':
                old = {n: r.get(n) for n in st[1]}
                r.set(**st[1])
                try:
                    r.commit(); fails.append(f'{name}: commit {st[1]} accepted, must be rejected')
                except CommitError:
                    pass
                r.set(**old)
            elif st[0] == 'status':
                v = r.status(st[1])
                if st[2] is not None and v != st[2]:
                    fails.append(f'{name}: {st[1]} = {v}, want {st[2]}')
                log(f'   {st[1]} = {v}')
        log(f'9 {name}: {"ok" if not fails else "FAIL " + fails[-1]} (ISLAND_STATUS 0x{r.read(A_ISLAND):04X}, CONFIG_ERROR {r.read(A_CFGERR)})')
    _teardown(r, touched)
    if fails:
        raise RuntimeError('9 ' + '; '.join(fails))
    return fails


def h2d_health(spi, chip, log=print):
    """H2D health (OBS-IMPL-6): sticky status.health.h2d_overflow / h2d_underflow must read 0 after training and traffic."""
    r = Regs(spi, chip)
    names = [n for n in STATUS if n.startswith('status.health.h2d')]
    if not names:
        log('8 H2D health: no status field yet (digital to add); H2D proven only by commands working at this rate')
        return None
    vals = {n: r.status(n) for n in names}
    bad = {n: v for n, v in vals.items() if v}
    log(f'8 H2D health: {vals} ({"ok" if not bad else "FAIL"})')
    if bad:
        raise RuntimeError(f'8 H2D health: {bad} (sticky until reset; rate too high or H2D_CLK not centred)')
    return vals
