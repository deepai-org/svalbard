# Routed external-passive LNA/mixer parent

This is the first physically routed Wi-Fi receive-path parent. It places the
16-finger common-source LNA core and the two-bank external-LO switching mixer,
then routes their shared LNA-drain/mixer-RF net in parent-owned high metal and
ties the two explicit body contacts with a parent-owned ground rail.

The parent retains the necessary early external boundary: 50-ohm RF source and
input coupling, 1.5 V LNA bias, 300-ohm drain load, source degeneration, 2.3
GHz complementary LO, and differential 100 MHz IF load/filter. The visible
`MIX_RF` port is intentional: it is the physical landing for that external
drain load, not an unmodeled ideal internal connection.

`run_parent_physical.sh` requires zero DRC errors, unique LVS, full-RC PEX and
five complete PVT transient conversions. This is a composed feasibility claim,
not a qualified 802.11 receiver: RF/passive model validity, matching, noise,
linearity, isolation, I/Q, LO generation, IF/baseband, package/antenna EM,
calibration, sensitivity, EVM and regulatory behavior remain open.

The same physical runner now also performs a bounded two-tone diagnostic: a
1 mV desired tone at 2.400 GHz and a 100 mV aggressor at 2.425 GHz enter the
same external 50-ohm source and are mixed by the same external 2.300 GHz LO.
Across the five PVT cases the desired 100 MHz IF Fourier component changes by
+0.065 dB or more, while the 125 MHz aggressor IF component is at least
39.872 dB above it. That is an observed pre-filter compact-model fact, not a
blocker-tolerance, linearity or adjacent-channel-rejection claim: it makes the
missing IF/baseband filter and model/measurement qualification explicit.
