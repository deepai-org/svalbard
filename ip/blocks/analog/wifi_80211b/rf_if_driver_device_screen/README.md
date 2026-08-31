# Wi-Fi IF-driver raw-device speed screen

This is a necessary compact-model screen for the next real-IF driver, not a
driver implementation. It finds each 3.3-V device's small-signal
drain-current/gate-current unity crossing at the DC trip point of the same bare
balanced push-pull stage already rejected as a complete output driver.

The screen compares those crossings with the 989.056-MHz one-pole settling
bandwidth implied by the 424.974-pF thermal-floor sampled load, 1.45-ns track
time, and quarter-LSB allocation. It requires a five-times margin merely to
authorize closed-loop IF-driver schematic work. It cannot establish a feedback
loop, distributed gate drive, large output bank, output settling, noise,
linearity, physical layout, or GF180 high-frequency model validity.

Run it with:

```sh
./run_probe.sh
```

The current 10-case result is bound in
[`device_speed_screen_result.json`](device_speed_screen_result.json). Its
limiting public-model case is the SS/hot PMOS at 8.037 GHz, 8.126 times the
required settling bandwidth. That clears only this necessary input-device gate;
the next artifact must be a complete closed-loop buffer schematic.
