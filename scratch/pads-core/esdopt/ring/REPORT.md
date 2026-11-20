# Provider-ring resistance for the pad_hspad ESD bench (a6), 2026-11-20

## Method
- Geometry: `$P/analog/pads/generated/packaging-assembly.gds` (sha256 5e836f93...), cell `retained_provider_ring`. pt_wired east edge:
  hspad sites bidir[14] (y 941-1016) and bidir[15] (y 1152-1227); near cells dvdd_pads[0] (519-594) and dvss_pads[1] (730-805);
  next cells dvdd_pads[1] (2207-2282) and dvss_pads[2] (2418-2493); every other provider cell is farther (other edges).
- Rail bands (`bands.py`): Metal3/4/5 full-length bands per tile, net from the 42/46/81 datatype-10 labels.
  Fill tiles: DVSS 101.4 um, DVDD 124.0 um per layer (rail tile under the sites: 103.0 / 128.8 um); VSS and VDD 14 um each.
  Per um of ring, M3 || M4 || M5 (90/90/40 mohm/sq typ, 104/104/49 high, Magic tech values per ESD-METAL.md / netres.py):
  | rail | typ mohm/um | high mohm/um |
  |---|---|---|
  | DVSS | 0.209 | 0.249 |
  | DVDD | 0.171 | 0.203 |
- Mesh extraction: `$P/analog/pads/rextract/netres.py` (spec `ring_spec.json`, out `ring_out.json`; terminals = M3-5 rail metal over the 75 um span of each cell, grouped).

## Known answer
Straight fill segment y 816-924 (108 um, fill10 only), `ka.json` -> `ka_out.json`:
hand 108 x 0.2089 = 22.6 mohm (DVSS typ), 26.9 (high); DVDD 18.4 / 22.0. netres: 0.023 / 0.027 / 0.018 / 0.022 ohm. PASS.
Second check site14-site15 alone (`p.json`): netres 28 / 23 mohm typ (DVSS / DVDD), hand 136 um x rate = 28.4 / 23.2. PASS.

## Extracted values (netres, long window 515-2497, edge-to-edge of the cell spans)
| path | DVSS typ / high | DVDD typ / high |
|---|---|---|
| site15 -> dvss1 | 0.049 / 0.058 | - / 0.050 |
| site15 -> dvdd0 | 0.073 / 0.087 | - / 0.075 |
| site14 -> dvss1 / dvdd0 | 0.024 / 0.029, 0.048 / 0.058 | - / 0.025, - / 0.050 |
| site15 -> dvdd1 / dvss2 (far) | 0.175 / 0.209, 0.199 / 0.238 | - / 0.177, - / 0.202 |
| dvdd0 -> dvdd1 | 0.248 / 0.296 | 0.252 (high) |
Caveat: in the long window the pairwise values are ~15 % below the two-terminal / hand values (24 vs 28 mohm for site14-site15);
the trace picks up Metal1/Metal2 of the provider and fill cells in parallel. Root cause not settled, so the bound below is built
from the hand rate (M3-5 only, which is higher) and centre-to-centre distances, not from these numbers.

## Pessimistic bound (stated)
High metal (M3-5 only, fill-tile rate everywhere, ignoring the wider metal in provider cells and the Metal1/2 bands),
farther site (bidir[15], centre 1189.5), centre-to-centre distances, lumped near node taken at the FARTHER near cell (dvdd0, 633 um) for
both rails, far node at the farther next cell (dvss2, 1899 um past dvdd0) for all far cells, then x 1.2 for landing position / crowding at
the site and the unmodelled site-to-site segment:
| | DVDD | DVSS |
|---|---|---|
| RN typ (hand, centre-centre) | 0.108 | 0.132 |
| RN high | 0.129 | 0.157 |
| **RN bound** | **0.155** | **0.189** |
| RF typ / high | 0.324 / 0.386 | 0.397 / 0.472 |
| **RF bound** | **0.46** | **0.57** |
Old assumption: 0.125 / 0.375 high (both rails); reviewer stress case 0.25 / 0.75. Also: the real ring has 6 dvdd + 8 dvss cells
(bond_map, provider-sites.json), the bench had 8 + 10; rerun uses the real far group (5 dvdd + 7 dvss, `--far 5,7`).
Side note: bond_map.txt says bidir[14]=WIRE_RX_N / [15]=WIRE_RX_P, provider-sites.json says [14]=WIRE_RX_P. Irrelevant here (bound uses the farther site), but the two disagree.

## Proposed row for spec/design-assumptions.md (text only, not entered)
| Provider-ring rail resistance, pt_wired hspad site (east bidir[14]/[15]) to provider clamps, ESD bench | DVDD near 0.155 ohm, DVSS near 0.189 ohm, DVDD far 0.46 ohm, DVSS far 0.57 ohm; far group = 5 dvdd + 7 dvss cells | Extracted from packaging-assembly.gds retained_provider_ring M3-5 bands (DVSS 0.249, DVDD 0.203 mohm/um high metal; netres.py known answer 22.6 mohm/108 um), scratch/pads-core/esdopt/ring/REPORT.md | Bound = high metal x 1.2 geometry, farther site, centre-to-centre, far cells lumped at the farthest east neighbour; extraction typ is 0.04-0.07 / 0.18-0.25 ohm |

## Rerun (a6 `sec/models/a6_r_high.spice`, `esd3.py` = esd2.py + per-rail ring + far count; --rxgate; CDM with --cdie 1n)
Control: esd3 default (= esd2 ring high) CDM 2 A P-N reproduces 7.313 V gate / 10.728 V diode (a6rh_cdie.json). PASS.
Limits: gate <= 8.0 V; RX-VSS, RX-VDD <= 5.0 V; nd2ps < 11 V, pd2nw < 10.5 V; MIM <= 6 V.
| case | worst gate V | diode rev V (type) | RX-VSS / RX-VDD V | MIM V | result |
|---|---|---|---|---|---|
| CDM2A P+VSS | 7.13 | 10.67 nd2ps | 4.05 / 2.68 | 5.22 | PASS |
| CDM2A P-VSS | 1.38 | 5.65 pd2nw | 1.47 / 1.85 | 3.19 | PASS |
| CDM2A N+VSS | 7.26 | 10.68 nd2ps | 4.06 / 2.70 | 5.29 | PASS |
| CDM2A N-VSS | 1.38 | 5.64 pd2nw | 1.48 / 1.85 | 3.23 | PASS |
| CDM2A P+VDD | 3.52 | 7.05 nd2ps | 1.67 / 1.63 | 4.57 | PASS |
| CDM2A P-VDD | 4.23 | 9.27 pd2nw | 2.18 / 4.26 | 3.19 | PASS |
| CDM2A N+VDD | 3.65 | 7.06 nd2ps | 1.69 / 1.65 | 4.65 | PASS |
| CDM2A N-VDD | 4.23 | 9.26 pd2nw | 2.19 / 4.27 | 3.23 | PASS |
| CDM2A P+N | 7.51 | **11.05 nd2ps** | 4.42 / 4.27 | 5.22 | **MISS (diode)** |
| CDM2A P-N | 7.64 | **11.06 nd2ps** | 4.44 / 4.27 | 5.29 | **MISS (diode)** |
| HBM2kV P+N | 5.43 | 7.16 nd2ps | 4.88 / 4.89 | 3.98 | PASS (RX 0.11 V margin) |
| HBM2kV P-N | 5.44 | 7.17 nd2ps | 4.87 / 4.87 | 4.02 | PASS (RX 0.13 V margin) |
Attribution: same bound with the bench's 16 far cells, CDM P-N / P+N: 7.63 / 7.50 V, 11.05 / 11.04 V: the miss comes from the ring R, not the cell count.
Gates hold everywhere (0 over 8.0 V). The nd2ps miss is 0.05-0.06 V over the model bv and is bv-model dependent (review finding 2: the
model's breakdown is clamping). Files: `esd/bound_cdm2.json`, `esd/bound_hbm2.json`, `esd/bound16_cdm2.json`, `esd/ctl_esd2default.json`, `runs.log`.

(DVDD typ rows of the long-window run were not kept in the log; only high is listed.)

## Primary diodes judged by current density and energy (coordinator ruling, 2026-11-20)
For the PRIMARY site diodes the criterion is peak current density and energy per finger against a stated rating; bv stays the criterion
for every other junction. `cur.py` = esd3 deck on the bound ring (0.155/0.189/0.46/0.57 ohm, far 5+7), a6 high model, --rxgate,
CDM with 1 nF; + savecurrents on all 20 site diodes (5 nd2ps + 5 pd2nw per pad, pj 51.8 um, area 22.5 um2 each). Energy = integral |V_d * I_d| dt over the run.
Files: `esd/cur_cdm2_PN.json`, `esd/cur_cdm2_PpN.json`, `esd/cur_hbm2_PN.json`, `esd/cur_hbm2_PpN.json`. Each run repeats the bound numbers (CDM P-N 11.061 V, P+N 11.052 V).

Limit: no foundry ESD diode rating was found locally (searched the GF180MCU PDK in the tool image (libs.ref/gf180mcu_fd_io, libs.tech),
scratch/transceiver-pad-pdk, spec/design-assumptions.md, scratch/reviews/pads-core). Literature: 100 ns TLP failure current of STI-bounded
junction diodes in forward conduction is typically 20-50 mA/um of perimeter (Amerasekera & Duvvury, "ESD in Silicon Integrated Circuits", 2nd ed.;
Voldman, "ESD: Physics and Devices"). Limit used: **10 mA/um forward** (bottom of that range / 2), **1 mA/um in avalanche** (reverse-mode It2 is several
times lower), both at 100 ns with **no credit** for the shorter 1 ns CDM pulse (Wunsch-Bell would allow roughly 3-10x more). Energy reference:
10 mA/um x 51.8 um x ~1.5 V x 100 ns = about 78 nJ per finger; the HBM 2 kV case (known good) is the comparison.

Per finger (all five fingers of a group carry the same value to 0.1 mA):
| Event | Fingers | Mode | Peak mA | mA/um | mA/um2 | Energy nJ | vs limit |
|---|---|---|---|---|---|---|---|
| CDM 2 A P-N | pd2nw N pad (D4,23,38,45,68) | forward | 375.1 | 7.24 | 16.7 | 2.02 | 72 % of 10 mA/um, PASS |
| CDM 2 A P-N | nd2ps P pad (D3,22,25,56,66) | forward | 362.7 | 7.00 | 16.1 | 1.92 | 70 %, PASS |
| CDM 2 A P-N | nd2ps N pad (D2,9,35,55,64), at 11.06 V | avalanche | 2.7 | 0.05 | 0.12 | 0.002 | 5 % of 1 mA/um, PASS |
| CDM 2 A P-N | pd2nw P pad, at 9.58 V | reverse | 2.6 | 0.05 | 0.12 | 0.002 | PASS |
| CDM 2 A P+N | pd2nw P pad | forward | 374.4 | 7.23 | 16.6 | 2.01 | 72 %, PASS |
| CDM 2 A P+N | nd2ps N pad | forward | 362.2 | 6.99 | 16.1 | 1.91 | 70 %, PASS |
| CDM 2 A P+N | nd2ps P pad, at 11.05 V | avalanche | 2.7 | 0.05 | 0.12 | 0.002 | 5 %, PASS |
| HBM 2 kV P-N (reference) | pd2nw N pad / nd2ps P pad | forward | 248.3 / 240.0 | 4.79 / 4.63 | 11.0 / 10.7 | 77.3 / 73.5 | 48 %, PASS |
| HBM 2 kV P+N (reference) | pd2nw P pad / nd2ps N pad | forward | 247.8 / 239.7 | 4.78 / 4.63 | 11.0 / 10.7 | 77.0 / 73.3 | 48 %, PASS |
| HBM 2 kV (both) | reverse-biased fingers, 6.2-7.2 V | reverse | 0.5 | 0.01 | 0.02 | 0.001 | PASS |

Reading: the 11.05-11.06 V reverse drop sits on fingers that carry only 2.7 mA (0.05 mA/um, 2 pJ); the event current passes in forward conduction
through the other polarity's fingers at 7.0-7.2 mA/um, 1.5x the HBM reference density but with 1/38 of its energy. Under the ruling, the two CDM
pad-to-pad cases change from MISS to **PASS (forward 72 % of a conservative 10 mA/um, avalanche 5 % of 1 mA/um)**. The limit is a literature
figure, not a foundry rating; the CDM peak density is above the known-good HBM density, so a TLP measurement of the site diode (planned TLP site) is the real check.

## PC-45: 1 nF ring decap at 0.7 ohm from the site (2026-11-20)
`esd3.py` option SITECAP (cur.py `--sitecap 1n,0.7`): CSITE 1 nF between DVDDSC and VSSSC, with **0.7 ohm on EACH rail** to the site landing nodes
DVDDS / VSSS (1.4 ohm loop: the pessimistic reading of "0.7 ohm incl. its own series R"; the far-node CDIE is not used). Ring at the bound
(0.155/0.189/0.46/0.57 ohm, far 5+7), a6 high model, receiver gate on. Ideal capacitor, no ESR beyond the 0.7 ohm.
Judged: gate <= 8.0 V; RX-VSS, RX-VDD <= 5.0 V; MIM <= 6 V; non-primary diodes (secondary pd2nw, clamp, rail diodes) reverse < bv (nd2ps 11, pd2nw 10.5);
primary site diodes peak <= 10 mA/um forward and <= 1 mA/um avalanche (pj 51.8 um). Files `esd/sc_*.json`, `sc.log`, `sc_table.txt`.

| run | gate V | RX-VSS / RX-VDD V | MIM V | non-primary diode rev V (frac bv) | primary fwd mA/um | primary aval mA/um (V) | energy nJ/finger | result |
|---|---|---|---|---|---|---|---|---|
| cdm2_P+VSS | 6.21 | 4.28 / 2.65 | 4.69 | 3.00 (0.29) | 7.22 | 0.052 (9.77) | 2.02 | PASS |
| cdm2_P-VSS | 1.11 | 1.47 / 1.57 | 3.19 | 1.01 (0.10) | 7.00 | 0.048 (5.28) | 1.92 | PASS |
| cdm2_N+VSS | 6.33 | 4.29 / 2.70 | 4.76 | 3.04 (0.29) | 7.23 | 0.052 (9.78) | 2.02 | PASS |
| cdm2_N-VSS | 1.10 | 1.48 / 1.58 | 3.23 | 1.01 (0.10) | 6.99 | 0.050 (5.27) | 1.92 | PASS |
| cdm2_P+VDD | 3.22 | 1.49 / 1.66 | 4.57 | 0.26 (0.03) | 7.22 | 0.050 (6.75) | 2.02 | PASS |
| cdm2_P-VDD | 4.28 | 1.89 / 4.52 | 3.19 | 4.03 (0.38) | 7.00 | 0.050 (8.34) | 1.92 | PASS |
| cdm2_N+VDD | 3.35 | 1.50 / 1.67 | 4.64 | 0.25 (0.02) | 7.24 | 0.050 (6.76) | 2.02 | PASS |
| cdm2_N-VDD | 4.28 | 1.91 / 4.52 | 3.23 | 4.03 (0.38) | 6.99 | 0.050 (8.33) | 1.92 | PASS |
| cdm2_P+N | 6.39 | 4.36 / 4.32 | 4.63 | 4.45 (0.42) | 7.22 | 0.052 (9.95) | 2.02 | PASS |
| cdm2_P-N | 6.52 | 4.37 / 4.32 | 4.71 | 4.44 (0.42) | 7.23 | 0.052 (9.96) | 2.02 | PASS |
| cdm1_P+N | 4.38 | 3.16 / 3.18 | 2.20 | 3.38 (0.32) | 3.61 | 0.035 (6.16) | 0.62 | PASS |
| cdm1_P-N | 4.45 | 3.16 / 3.18 | 2.23 | 3.38 (0.32) | 3.61 | 0.035 (6.17) | 0.62 | PASS |
| cdm3_P+N | 7.82 | 5.41 / 5.40 | 6.52 | 5.26 (0.50) | 10.49 | 1.116 (12.48) | 3.95 | MISS |
| cdm3_P-N | 7.99 | 5.42 / 5.39 | 6.62 | 5.25 (0.50) | 10.51 | 1.120 (12.48) | 3.96 | MISS |
| hbm2_P+N | 4.81 | 3.33 / 3.32 | 3.98 | 3.52 (0.34) | 4.78 | 0.010 (7.16) | 77.05 | PASS |
| hbm2_P-N | 4.90 | 3.33 / 3.32 | 4.02 | 3.52 (0.34) | 4.79 | 0.012 (7.16) | 77.27 | PASS |

CDM 2 A (all 10 cases), CDM 1 A and HBM 2 kV pad-to-pad: PASS. The site cap lowers the CDM 2 A pad-to-pad gate from 7.64 to 6.52 V and the
primary reverse from 11.06 to 9.96 V; primary forward density is unchanged (7.2 mA/um).
CDM 3 A pad-to-pad: MISS on four counts: RX 5.42 V (> 5.0), MIM 6.62 V (> 6.0), primary forward 10.5 mA/um (> 10), avalanche 1.12 mA/um at 12.5 V (> 1).
Gates hold (7.99 V, 0.01 V margin). 3 A is beyond the 2 A requirement; reported as information.
