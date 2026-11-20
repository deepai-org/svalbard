"""Reference bring-up sequence, spec/bring-up.md sections 1-6 (steps cite the section). Board-independent: needs an
`spi` (xfer) and a `board` with reset(low: bool), wait_us(t) and optionally clk_obs_hz(). Returns a dict of findings;
raises on a failure that stops bring-up."""
from regs import Regs, ID, ABI, HASH, CHIP_ID, A_ID, A_ABI, A_HASH, A_ISLAND, A_FAULT, A_RESET, A_CFGERR

RING_TT_330 = 210.5e6           # bring-up.md section 6 (extracted pt_ring_osc, tt, 3.30 V, 27 C)
ISLAND_BIT = {'wired': 0, 'rf': 1, 'pll': 2, 'conv': 4, 'debug': 5}
PAYLOAD = {'rf': ('rf', 'conv'), 'wired': ('wired',)}


def trim_choice(s):
    """Supply setpoint from the speed index S = f_ring / f_ring(tt, 3.30 V) measured at 3.30 V (section 6)."""
    return 3.50 if s < 0.91 else 3.20 if s > 1.09 else 3.30


def run(spi, board, chip, f_ref, log=print):
    r, out = Regs(spi, chip), {}
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
    log('4 bias on (256-SCLK interlock clocked); trims need the ATB1 SMU: codes 55, 57')
    # 5. islands one at a time: debug, pll, payload groups; effective-on and pgood both set
    want = 0
    for isl_name in ('debug', 'pll') + PAYLOAD[chip]:
        r.set(**{f'debug.island_power.{isl_name}': 1}); r.commit(); board.wait_us(20)
        b = ISLAND_BIT[isl_name]; want |= (1 << b) | (1 << (b + 8))
        got = r.read(A_ISLAND)
        if got != want:
            raise RuntimeError(f'5 island {isl_name}: ISLAND_STATUS 0x{got:04X} != 0x{want:04X}')
        log(f'5 island {isl_name} on, ISLAND_STATUS 0x{got:04X} (record the supply-current step)')
    # 6. speed indicator: ring_osc on the counter (cross-check path; CLK_OBS is primary, OBS-2)
    r.set(**{'debug.replica.ringosc_enable': 1, 'debug.clk_obs.source': 10, 'debug.clk_obs.divider_log2': 2}); r.commit()
    f_ring = count(r, board, 3, f_ref)
    if hasattr(board, 'clk_obs_hz'):
        f_ring = 4 * board.clk_obs_hz()
    s = f_ring / RING_TT_330
    out.update(ring_hz=f_ring, speed_index=s, supply_setpoint=trim_choice(s))
    log(f'6 ring_osc {f_ring/1e6:.1f} MHz, S = {s:.3f} -> supply setpoint {out["supply_setpoint"]:.2f} V')
    return out


def count(r, board, source, f_ref, window_code=1):
    """Frequency counter a on `source`; returns the source frequency from the last window count."""
    window = (256, 1024, 2048, 4096)[window_code]
    r.set(**{'debug.freq_count_a.source': 0}); r.commit()
    r.set(**{'debug.freq_count_a.source': source, 'debug.freq_count_a.window': window_code}); r.commit()
    board.wait_us(3.2 * window / f_ref * 1e6)        # first window only sets the reference point
    n = r.status('status.freq_count_a.count')
    return n * f_ref / window
