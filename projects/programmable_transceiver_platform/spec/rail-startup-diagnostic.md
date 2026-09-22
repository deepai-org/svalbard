# Pass 13: isolate quiet-input rail startup

Four fresh, bounded one-nanosecond runs compare ideal rails, supply-only impedance, return-only impedance and both. Each active rail uses the same selected 0.25 ohm/2 nH series path from pass 12. The native 8 mA pads, unequal signal inductances and 10 pF loads remain. Data and clock inputs are held low, matching the prior stimulus before its 20 ns start. Core supply/return remains ideal.

All four DC operating points and short transients complete with default integration and a 10 ps maximum step. Reported VDD is 3.3 V; quiet source current is approximately 0.71 nA. The both-rails case has VSS between −0.024 and +0.395 nV, and low output voltage around 3.35 nV. These tiny model residuals do not establish physical noise accuracy.

| Case | Saved transient rows | Completed simulated time |
|---|---:|---:|
| Ideal | 108 | 1 ns |
| Supply only | 329 | 1 ns |
| Return only | 287 | 1 ns |
| Both | 391 | 1 ns |

This rules out an obvious large startup rail excursion **in the captured interval**. It does not explain the later slowdown, prove stability beyond 1 ns, or test switching. More adaptive points with R/L are observed, but their count alone is not a diagnosis. Prior full-interval timeouts remain unresolved, including those using Gear.

Run `verification/run_rail_startup.sh` from this project. Each probe has a 30-second subprocess limit and records completion separately from waveform availability. The [retained report](../evidence/rail-startup-screen.json) includes deck/log/operating-point/waveform hashes. The raw archive is `scratch/transceiver-rail-startup-artifacts.tar.gz`.

Next preserve intermediate waveforms as simulated time approaches the slowdown, inspect timestep and rail/internal-node behavior, and compare the supply-only/return-only cases over that same interval. Do not infer that more damping is the correct physical fix before distinguishing numerical behavior from circuit behavior. Follow the [two-sided uncertainty requirement](uncertainty-envelope.md): both apparent stability and apparent instability need scrutiny.

Archive SHA-256: `1327697b4462f4ae991e1670b4fbd06aa5fcb6e3ed91b8b88bb87d0ed8633b6e`.
