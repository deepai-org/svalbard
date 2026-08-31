# First closed-loop Wi-Fi IF-driver topology screen

This is the first actual closed-loop schematic candidate after the thermal,
output-bank, and raw-device screens. Two differential lanes use five tapered
CMOS inverter stages and direct equal-resistor feedback. The odd stage count
makes the differential path inverting and the feedback negative. Its purpose
is to test whether a real transistor feedback loop can settle a full-scale
250-mV differential step into two 424.974-pF loads in 1.45 ns.

This is a deliberately bounded screen. It has no extracted layout, no output
bank gate distribution, no active CMFB, no loop-stability proof, and no noise,
linearity, ADC, or receiver claim. A passing result would only justify adding
those mechanisms before layout; a failure identifies the first actual
closed-loop circuit limitation.

Run it with:

```sh
./run_probe.sh
```

The initial result is a useful rejection, bound in
[`inverter_loop_rejection.json`](inverter_loop_rejection.json): all five cases
complete but fail. The best differential step error is 239.354 mV against the
30.518-uV allocation, common mode moves by up to 1.809 V, and the static draw
reaches 3.156 A. The next candidate must have an explicit error amplifier,
CMFB, compensation, and a current-limited class-AB or source-follower output
stage; it must not be an inverter-chain tuning exercise.
