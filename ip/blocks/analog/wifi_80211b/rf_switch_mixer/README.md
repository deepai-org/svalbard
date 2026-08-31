# 2.4 GHz external-LO switching-mixer risk macro

This is the second Wi-Fi receive-side physical feasibility primitive. It is a
two-bank NFET commutating mixer with external 2.3 GHz complementary LO drives,
a 2.4 GHz 50-ohm RF source, and external 100 MHz differential IF loads. The
cell deliberately contains neither a VCO/PLL, balun, RF or IF matching/filter,
baseband amplifier, calibration, nor a package/antenna model.

`run_mixer_physical.sh` creates the physical two-bank array, runs DRC, LVS and
full-RC PEX, then performs the five-corner transient conversion screen. A
passing result means only that a finite 100 MHz differential component was
measured under this declared external bench. Noise, linearity, LO/RF/IF
isolation, I/Q balance, mixer conversion efficiency, model validity, and
receiver sensitivity remain open obligations.
