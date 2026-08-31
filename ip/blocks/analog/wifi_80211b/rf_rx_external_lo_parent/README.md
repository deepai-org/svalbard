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
