# Bring-up reference software

Plain Python implementation of `spec/bring-up.md` sections 1-6 over an abstract SPI (`xfer(cmd, addr, data)`) and
board (`reset(low)`, `wait_us(t)`, optional `clk_obs_hz()`), driven by the generated register map
(`spec/register-map.json`).

- `regs.py`: field writes on a host shadow, commit with the ERROR_INFO check, status reads, SCLK padding (B54).
- `sequence.py`: power-up/reset, identity (ID, ABI, MAP_HASH, `status.chip.id`), aosc and REF_IN on the frequency
  counter, bias with the 256-SCLK rule, islands one at a time, ring-oscillator speed index and the supply setpoint.
- `sim_rtl.py`: RTL back-end. Builds a bench from the instantiation in `integration/chips/sim/tb_top_modes.sv` (real
  `pt_digital_macro` with `PT_CHIP`, generated stub analog top), drives SPI from Python through vvp stdin.

```
python3 tools/bringup/sim_rtl.py rf                      # PASS, 210.5 MHz ring -> 3.30 V
python3 tools/bringup/sim_rtl.py rf --ring-mhz 173.8     # ss ring -> 3.50 V
python3 tools/bringup/sim_rtl.py wired --negative        # builds pt_rf: chip-id check must stop it
```

Not covered yet: host-link training (needs ring and CDR models in the stub), ATB readings (need a test-board SMU
back-end), per-mode sequences. The stub's POR is constant, so `RESET_STATUS` b0 reads 0 in simulation.
