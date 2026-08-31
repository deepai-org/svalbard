# Die-side RF open/short/thru/load coupon

This is a physical calibration coupon for the 2.4 GHz Wi-Fi risk track. It
contains geometrically comparable G-S-G M5 landing structures for open, short,
thru and a P+ poly load. `THRU_A`, `THRU_B`, and `SHORT` are labels on
intentional physical shorts; `OPEN`, `LOAD`, and `VSS` are the LVS-visible ports.

Run it with:

```sh
./ip/blocks/analog/wifi_80211b/rf_ostl_coupon/run_coupon_physical.sh
```

The flow requires zero DRC errors, a unique LVS match, and full RC PEX. Its PDK
model has an explicit floating poly-body terminal, so the generated evidence
checks the extracted topology rather than pretending a lumped DC simulation
qualifies RF impedance. The flow preserves the actual PEX and a reviewable
layout render. The accompanying [`test_plan.json`](test_plan.json) defines the
0.1--6 GHz measurement and de-embedding obligations for silicon.

This is not a production pad, a calibrated 50-ohm standard, an EM result, or
proof of Wi-Fi receiver performance. Qualified probe/pad/package/antenna
networks and measured S-parameters remain requirements before the coupon can
reduce the RF model-validity obligation of the receive parent.
