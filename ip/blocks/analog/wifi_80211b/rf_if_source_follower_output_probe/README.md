# Wi-Fi IF class-AB source-follower output primitive

This screen asks one narrow question after the inverter-loop rejection: can a
complementary source-follower output bank provide the 0.379-ohm small-signal
output impedance with a finite, externally declared class-AB gate separation?
It sweeps four output widths and six gate separations over the five public PVT
environments, recording DC output common mode, static supply draw, and 100-MHz
output impedance.

The two gate voltages are testbench sources. This is not a complete IF driver,
CMFB, bias generator, gate distribution, large-signal settling, or physical
layout claim. It decides only whether this output-stage family should be used
by the next compensated differential error-amplifier schematic.

```sh
./run_probe.sh
```

The byte-bound outcome is
[`source_follower_output_result.json`](source_follower_output_result.json).
With ideal gate biases, the 20-mm NMOS / 40-mm PMOS, 2.6-V-separation setting
passes output impedance in every corner, but draws up to 0.991 A per output and
leaves 155.777 mV of common-mode error. That is enough to retain this
output-stage family for a calibrated low-Iq search, not enough to promote it to
an IF-driver implementation.
