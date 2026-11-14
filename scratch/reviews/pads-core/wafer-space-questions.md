# Questions for wafer.space (chip-on-board, GF180MCU 1x1 slot, 74-pad ring)

2026-11-14. Eleven questions, each with one line of why it matters. Background numbers are in `BOND-AUDIT.md`, `SITES.md` and
`../rails/RAIL-CONTINUITY.md`. Our reference is `chip-on-board-wire-bonded-pcbs` at commit `5cb4668` (run-2 1x1 mezzanine).

1. Which COB board (run and revision) will the next shuttle's 1x1 dies be bonded to, and are its finger coordinates, paddle size and the wirebonding rules in `run-1/wirebonding/README.md` final for that run?
   - Why: our bond audit passes with 9 um of length margin on the run-2 file; run-1 and run-2 differ in the ground copper inside the finger ring, which decides whether a ground down-bond is possible.

2. Do you accept a custom bond diagram per design, and can it differ per die (for example a bond present on some dies and absent on others)?
   - Why: we want to leave some pads unbonded and add two bonds that are not in the default 74; a per-die option would let one strap be set at assembly.

3. May a pad be left unbonded, and may we add bond-pad openings beyond the 74 template sites (two extra 60 um pads between template pads on the west edge, 76 to 135 um centre-to-centre from their neighbours)? What is the minimum bond-pad pitch and opening size you can bond?
   - Why: the two extra pads are planned as a separate LNA ground; at the planned position one opening is 16.5 um from its neighbour's opening.

4. Are ground down-bonds allowed, and onto what: the die paddle (only 34 to 39 um shows beside the die), or the bare GND copper between the paddle and the fingers on the run-2 board (a 1.0 to 1.9 mm wire)? Is that copper plated for bonding?
   - Why: the rules ask for at least 1 mm of wire and do not mention down-bonds; the LNA ground needs the shortest possible return.

5. Are two wires on one finger allowed (a second pad bonded onto a neighbouring GND finger, about 2.5 mm, 30 degrees)?
   - Why: on the run-1 board this is the only rule-compliant ground landing for an extra pad.

6. How are the 3 mm and 45 degree limits measured (plan view or wire length, from pad centre to where on the 1.0 x 0.25 mm finger), and what are the die placement tolerance and the loop height?
   - Why: with finger-centre landing our corner bonds are 2.991 mm in plan and over 3 mm as real wire; with near-end landing the corner angle is 44.0 degrees; a 0.1 mm die shift breaks one limit or the other.

7. What is the die thickness after back-grind, is the die attach conductive, and is the paddle (die back side) connected to board GND?
   - Why: the minimum wire length is 2 x die thickness, and a conductive attach ties our p-substrate to board ground, which changes the substrate noise and ESD return picture.

8. What wire (material, diameter) is used, and what continuous current per bond and per connector contact do you rate it for?
   - Why: our worst supply bond carries about 88 mA and we are deciding whether to give up a signal pad for one more supply bond.

9. Which GF180MCU process options and devices does the shuttle build: native-Vt NAT (`nfet_06v0_nvt`), DNWELL, SAB / ESD devices `nfet_06v0_dss` and `pfet_06v0_dss` outside the provider IO cells, 1k high-res poly `ppolyf_u_1k`, MIM `cap_mim_2f0_m4m5_noshield` (2 fF/um2 between Metal4 and Metal5), `cap_nmos_03v3_b`? Is anything in gf180mcuD not manufactured or checked differently by the precheck?
   - Why: all of these are in our layout (regulator pass devices, PA isolation, custom ESD cells, decoupling); a missing implant or module would not show in DRC.

10. May the ring contain custom pad cells in place of the provider IO cells (same 60 um openings on the template positions, provider rail cell kept underneath), and is the on-die short between all DVDD / VDD pads and between all DVSS / VSS pads that the stock `dvdd` / `dvss` cells make the intended behaviour (board nets VDD_IO, VDD_CORE and PWR_AUX become one die net)?
    - Why: 24 of our 74 pads are custom cells, and our supply plan treats the whole ring as one supply net and one ground net.

11. Can the die attach be electrically conductive (silver epoxy or similar) onto the 4.0 x 5.2 mm paddle with the paddle tied to board GND, so that the die back side is grounded, and what are the back-side finish (bare ground silicon, polished, back metal) and the final die thickness? (Sharpens question 7.)
    - Why: our substrate-coupling study gives a grounded die back side 20 to 45 dB of extra isolation between blocks 0.5 mm or more apart, and the same grounded paddle is the image plane that our bond-wire coupling numbers assume (the bound without it is 2 to 8 times more mutual inductance between RF bond pairs); a non-conductive attach or an oxidised back side loses both.
