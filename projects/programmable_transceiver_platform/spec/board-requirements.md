# Board requirements from the tapeout work

These are obligations on the bring-up and product boards that the die relies
on. Each was created by a design decision or a silicon limitation recorded in
`tapeout-readiness.json`. The external-component allowance in the
[pin plan](../../../docs/roadmap/programmable-transceiver-pin-plan.md) permits
all of them.

| ID | Requirement | Why | Source |
|---|---|---|---|
| B1 | **Reset supervisor IC on `RESET_N`**, open-drain, threshold inside the 3.15–3.35 V window. It holds the chip in reset on slow ramps and brownout. | The on-chip POR only covers cold start and full power cycles. It misses some 100 ms–1 s ramps and ignores dips that stay above 1.5 V. | `analog/core_support` evidence |
| B2 | **Supply 3.3 V ±1% from one source**, with the board decoupling the provider footprints expect. Junction temperature 27 °C ±5 °C; use cooling or heating if needed. | Operating envelope. | `tapeout-plan.md` |
| B3 | **Passive external LO (RF baseline):** I on `REF_IN`/`REF_IN_N`, Q on `AUX_CLK_P/N`, sine at 2.4–2.5 GHz, about 2 Vpp per leg at the pad, AC-coupled, through a matching network. Each receiver input is about 345–377 fF differential, roughly −j180 Ω at 2.45 GHz. Do not drive a sharp square wave. | Passive LO route `pt_lo_ext`. A square wave pumps its bias node. | `analog/timing` lo_ext evidence, `analog/pads` debug-sites |
| B4 | **DC-block `RF_TX`** (balun or series capacitor). Use the recommended L-match and balun from `analog/rf_tx/README.md` for rated output power. | The driver sits at about 2.4 V common mode and pushes up to 29 mA into a DC-coupled ground load. A DC source on an unpowered pad back-powers the RF island. | `analog/rf_tx` evidence |
| B5 | **Board LNA ahead of `RF_RX`** when sensitivity matters, plus the L-match on `RF_RX`. | Measured chain NF (with noise folding) is 12.1 dB with the board match, and 2.8 dB with a 15 dB / 1.5 dB board LNA. | `analog/rf_rx` evidence |
| B6 | **Host lines must be high-impedance while the chip is unpowered.** Preferably use a bus switch with powered-off isolation on the 12 D2H/MISO lines. Never leave the chip supply floating while the FPGA is powered. | The provider host pads backfeed about 6.8 mA per pin (about 81.6 mA total) into the ring. With the supply floating, that risks partial power-up and latch-up. Series resistors are acceptable only on `HOST_MISO`. | `analog/pads` powered-host-backfeed |
| B7 | **Analog test bus force (`ATB0`/`ATB1`) only while the chip is powered**, or with the source limited to 1 mA. | Unpowered, a 50 Ω source pushes 54–56 mA into the ring through the provider analog pad. | `analog/pads` atb-provider-pad-force |
| B8 | **USB low speed through an external PHY.** USB full speed and high speed can use the chip. | On-chip LS edges are 33–67 ns against the required 75–300 ns. | `analog/pads` usb-attachment |
| B9 | **TMDS needs external 50 Ω pull-ups to 3.3 V** on `WIRE_TX_P/N`. | TMDS is a wired TX configuration with on-chip termination off. | `consolidation-pass.md` item 4 |
| B10 | **Board pads and test points for every debug site** (`BB_I/Q`, `AUX_CLK`, `WCLK_IN`, `WTX_EXT`, `WMON`, `CLK_OBS`, `DBG_OBS0/1`, `WCLK_OBS`, `WDBG_OBS`, `ATB0/1`, `ESD_TEST`). Each needs an SMA or probe point and an optional external ADC/DAC, clock source or upconverter. | Fallback routes and observability. | `tapeout-plan.md` tier 3 |
| B11 | **USB HS amplitude calibration per board:** set the HS bias DAC code at the board's actual rail and load by measuring HS amplitude (360–440 mV target). | Amplitude moves about 0.3 mV per mV of supply, and ss/3.15 V reaches only 372–379 mV at full scale. | `analog/pads` usb-hs-gate-sweep |
| B12 | **External serial data on `WTX_EXT` (wired TX fallback):** AC-couple it, and have the FPGA send at least 128 bits of balanced data (for example 1010) before the payload. Rates 0.5–1.6 Gb/s at 300–800 mVpp. | The coupling capacitors hold the previous level for about 40 ns, which causes start-up wander. | `analog/timing` diff_clk_rx data mode |
