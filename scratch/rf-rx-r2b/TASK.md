# Task B (RF RX owner's helper): fallback external-LNA path, external-LO leak at site B, ESD at the LNA gate, MOS capacitor stress

Repo /home/ubuntu/svalbard, project projects/programmable_transceiver_platform. LNA: analog/rf_rx (netlists.py lna(), generated/
lna.ext.spice, benches tb.py / lna_match.py / lna_close.py; notes scratch/rf-lna-q/NOTES.md; README sections 4 (lna), 5a, 6).
Rules: scratch/reviews/MANDATE.md sections 2, 3, 4, 6, 8. Package: spec/package-channel.md, pads owner's model
scratch/reviews/pads-core/LNA-GROUND.md + lna-bond-model.spice (site option B is the decided bond map: RF_RX on bonds 67/68).

Deliver numbers with stated limits (declare the limit before each run; include one negative control per bench):
1. **Fallback external LNA through the bypass path** (never simulated): `byp` = 1, `en` = 0: RF pads -> series MIMs -> bypass
   switches -> both mixer feeds (see lna() in netlists.py). An external LNA on the carrier (assume gain 15 dB, NF 1.0 dB, 50 ohm
   single-ended output through a balun to 100 ohm differential; state the assumption, give the result also for gain 12 and 20 dB)
   drives the real channel (`lna_match.channel_ladder` / `channel_fit`: carrier parts -> connector -> COB trace -> bond -> pad).
   Wanted: input impedance at the pads in bypass (tb.lna_ac mode 'bypass' gives Zin and gain into the 50 ohm mixer model), best
   carrier match, loss from the external LNA output to the mixer feeds, and the resulting system noise figure estimate at the
   antenna against RF-RX-NFSYS (8 dB incl. 3.91 dB board budget: spec/performance-requirements.md). The mixer + TIA noise
   referred to the mixer feed can be taken from the owner's chain rows (`scratch/rf_rx/close_L6/chain.json` and
   `scratch/rf-lna-q/old_L5/*.json`: f_parts are noise-factor contributions, gain_sig_db is source EMF -> TIA output) or from
   tb.ota_input_noise / tb.rxmix_tran; say exactly how you derived it. AC / noise / op runs preferred; at most ONE transient of
   <= 30 min if you really need a conversion-gain point in bypass (tb.chain_tran mode 'bypass').
2. **External-LO leak into the RX pair at site B**: pads owner gives the pad-pair mutuals (AUX_CLK / REF_IN pair to RX pair:
   site A 2.2 / 0.9 pH, site B 6.1 / 2.2 pH nominal; LNA-GROUND.md section 4, bondl data in scratch/pads-core/lnagnd/). With the
   decided ~1 Vpp external-LO drive into the LO pads (find the pad load / current in analog/timing README or the LO owner's
   notes), compute the differential EMF induced in the RX pair at 2.4-2.5 GHz, refer it to dBm at the RF_RX port (limit
   RF-RX-LOLEAK -57 dBm) and to DC offset at the TIA output through the LNA (source EMF -> TIA output gain ~31 dB at tt from the
   owner's chain row) against the TIA offset-DAC range (netlists.py ofsdac / README). Min / nom / max.
3. **ESD at the LNA gates**: the CS gates sit behind 47 um input MIMs (4.4 pF) with 60 kohm bias resistors and no secondary
   clamp. Use the pads owner's HBM bench (analog/pads/hbm_core_screen.py, as used for bb_tap, and whatever pad model it uses for
   pad_rf_pair) to get the gate-oxide voltage of the 3.3 V CS devices (Vgs, Vgd, Vgb) during a 2 kV HBM pulse on RF_RX_P (both
   polarities, LNA unpowered), against the transient oxide limit the pads benches use. If it fails, size the smallest secondary
   clamp at g_p / g_n that passes (e.g. small gate-grounded NMOS or diode pair to VSS, give W and its capacitance) - as a
   proposal with numbers only; DO NOT edit netlists.py.
4. **19 pF NMOS gate capacitor on `vtk` and the always-on feed PMOS**: oxide field / lifetime statement at 3.63 V DC (and at the
   3.50 V trim setpoint) from PDK data (the PDK and reliability rules available under the repo / docker image; cite the source,
   say plainly if no TDDB data exists), and the alternative (6 V device cap: area factor) if the margin is not defensible.

Machine rules: shared box. AT MOST ONE simulation at a time, `OMP_NUM_THREADS=1`. DO NOT start any simulation until the file
/home/ubuntu/svalbard/scratch/rf-lna-q/GO exists (do reading, numpy work and deck preparation first; then poll for it with short
loops). Work only in /home/ubuntu/svalbard/scratch/rf-rx-r2b/ (copy helpers there; point work directories there). Do not edit
project files, do not commit. No report files: return the results as a plain-text reply (<= 700 words) with a table per item,
what was run versus estimated, and every assumption.
