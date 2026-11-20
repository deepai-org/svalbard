# Bring-up reference software

Plain Python implementation of `spec/bring-up.md` sections 1-9 (all modes of section 9 per chip) over an abstract SPI (`xfer(cmd, addr, data)`) and
board (`reset(low)`, `wait_us(t)`, optional `clk_obs_hz()`), driven by the generated register map
(`spec/register-map.json`).

- `regs.py`: field writes on a host shadow, commit with the ERROR_INFO check, status reads, SCLK padding (B54).
- `sequence.py`: power-up/reset, identity (ID, ABI, MAP_HASH, `status.chip.id`), aosc and REF_IN on the frequency
  counter, bias with the 256-SCLK rule, islands one at a time, ring-oscillator speed index and the supply setpoint;
  host link (TX-ring host follow, div4, slow slew + stagger, training by ENABLE restarts while the FPGA sweeps its
  capture delay); modes (`sequence.MODES`, from tb_top_modes sections 2-7): pt_rf receive with external LO, transmit/duplex, on-chip LO;
  pt_wired transmit (`status.wired.tx_state` = run), receive, USB full speed; each with its rule-rejection negative
  control; H2D health check (reports 'not available' until digital adds the status bit).
- `atb.py`: ATB1 sense model (switch path from the RTL, leaves from the chip conn, meter of
  `spec/test-board/tb_models.spice` `tb_atb_meter`) and the expected values / limits of bring-up.md section 10.
- `sim_rtl.py`: RTL back-end. Builds a bench from the instantiation in `integration/chips/sim/tb_top_modes.sv` (real
  `pt_digital_macro` with `PT_CHIP`, generated stub analog top), drives SPI from Python through vvp stdin. The
  FPGA model loops D2H back into H2D and captures D2H on the forwarded clock after the trained delay. The host word
  clock runs only if the software programmed the clock path the RTL decodes (PS_H2D, TX ring EN, prescaler /4, HS_INT).

```
python3 tools/bringup/sim_rtl.py rf                      # PASS, 210.5 MHz ring -> 3.30 V
python3 tools/bringup/sim_rtl.py rf --ring-mhz 173.8     # ss ring -> 3.50 V
python3 tools/bringup/sim_rtl.py wired --negative        # builds pt_rf: chip-id check must stop it
python3 tools/bringup/sim_rtl.py rf --negative-host      # host prescaler /8: training must fail
python3 tools/bringup/sim_rtl.py rf --negative-atb       # sense a code with no leaf on pt_rf: must read open
```

Not covered yet: pad timing (the RTL window is ideal: every tap passes), H2D checking (no H2D status bit; the pattern
checker is pt_wired-only), analog behaviour behind the stub (block currents, LO lock, ADC data: bench only). The stub's POR is constant, so `RESET_STATUS` b0 reads 0 in simulation.
