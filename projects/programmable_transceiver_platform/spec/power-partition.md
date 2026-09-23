# Power allocation revision, pass 6

## Candidate allocation within 50 terminals

Preserve all 36 signal terminals and 14 supply/ground terminals. Reassign `VDD_CORE_1` / `VSS_CORE_1` to `VDD_HOST_1` / `VSS_HOST_1`. The host now has two dedicated supply/return paths, and the core has one. This is a candidate tradeoff, not proof that the core can spare a path.

| Domain | Supply/return pairs | Planning ceiling per connection | Evidence state |
|---|---:|---:|---|
| Core/control and I/O pre-drivers | 1 | 48 mA | No implemented-core power estimate |
| Host output-driver segments | 2 | 55 mA | Limited two-pad-current extrapolation only |
| Wired analog | 2 | 48 mA | Distribution and complete lane current unclosed |
| RF analog | 1 | 48 mA | Full RF/converter current unclosed |
| PLL/reference | 1 | 48 mA | Full clock-engine current unclosed |

These ceilings are engineering targets beneath the provisional 60 mA supply-cell DC limit. They do not imply that the foundry has approved these operating conditions or that rail/package/thermal limits are met. The source of the cell limit is the [GF180 I/O library datasheet](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html); its use for the eventual selected process, pad and temperature envelope requires confirmation.

The core target is now at most 48 mA through its sole supply/return pair, including SRAM/FIFO, GPIO pre-drivers, transport and shared control. If synthesis/activity simulation and physical power analysis exceed it, revise the whole allocation before freeze. Do not claim that relocating the supply pair solved chip power.

## Host segmentation and physical requirements

`HOST_A` owns D2H data 0–4 and H2D data 0–4, plus SPI/reset pad circuitry. `HOST_B` owns D2H data 5–9, D2H clock, H2D data 5–9 and H2D clock. A and B each have one dedicated supply pad and one dedicated return pad. They use the same nominal board I/O voltage, but output-driver rail segments must have explicitly routed local feeds and returns. Their electrical connection on the board does not justify assuming equal on-die current division.

The [native netlist audit](../evidence/supply-cell-audit.json) records these formal pins:

- `gf180mcu_fd_io__dvdd`: `DVDD DVSS VSS`.
- `gf180mcu_fd_io__dvss`: `DVDD DVSS VDD`.
- `gf180mcu_fd_io__brk2` and `__brk5`: `VSS`.

Digital pad output devices use `DVDD/DVSS`; pre-drivers use `VDD/VSS`. The candidate rail map connects each host output-driver segment to its own HOST feed/return and pre-driver rails to CORE. Supply-cell clamps and corner cells have cross-rail connections that must be explicitly instantiated and verified. The formal-pin audit is **not** proof of physical rail continuity or isolation: inspect LEF/GDS, breaker placement, well/substrate paths and actual metal connectivity before layout acceptance. Keep short return paths for each D2H clock/data group. Clock/data loading, rail differences and deskew must be evaluated across the segment boundary.

This revision adds neither a hidden paddle nor an uncounted supply terminal. Bond-wire peak current, inductance and ground bounce are independent of the DC ceiling and remain open.

## Limited current screen

`check_power.py` uses the saved pass-5 alternating-pattern pair currents, divides by two for an identical output estimate, and scales by five or six outputs. It then applies a **provisional** 1.25 multiplier plus 2 mA per segment for unmodeled activity. These allowances are assumptions, not measurements or guaranteed guard bands.

| Corner / segment | Scaled average | With provisional allowances | Candidate ceiling |
|---|---:|---:|---:|
| TT / A (5 fast outputs) | 33.18 mA | 43.47 mA | 55 mA |
| TT / B (6 fast outputs) | 39.82 mA | 51.77 mA | 55 mA |
| SS / A | 29.38 mA | 38.72 mA | 55 mA |
| SS / B | 35.25 mA | 46.07 mA | 55 mA |

The [retained assessment](../evidence/host-power-allocation-screen.json) hashes the exact contract and input report. It marks **every domain unqualified**. Tests reject duplicated/missing supply ownership, duplicated outputs, the prior single-host-pair allocation and an increased-current counterexample. No runtime gate interprets the planning screen as physical signoff.

The next physical pass must include FF/high-voltage current, input-bank activity, clamp/rail behavior and explicit package impedances. The current TT/SS ideal-supply pair result cannot bound those cases. In parallel, actual RTL/memory selection must produce an activity-based core-power estimate; copying a pad from CORE is not a substitute for that evidence. A full-bank transistor run should then replace the linear estimate and test both in-phase and opposing group activity.

## Pass 8 limitation

The [8 pF host screen](artix-host-load-screen.md) exceeds HOST_B's planning ceiling after the existing allowances (63.54 mA versus 55 mA), even at nominal temperature and voltage. The two-segment allocation remains a candidate and is not closed for this load. Passing the earlier 5 pF executable screen does not supersede this negative evidence.

Pass 9 [native driver comparison](host-driver-selection.md): 12 mA mode reduces the same 8 pF HOST_B estimate to 55.75 mA with unchanged allowances, still above 55 mA. No driver or current ceiling is changed by this experiment.

Pass 10 [8 mA candidate](weak-drive-screen.md): the nominal 10 pF HOST_B estimate is 53.80 mA with unchanged allowances. This passes the limited planning comparison but leaves only 1.20 mA headroom; no package/bank/operating-envelope closure is implied.

## Coupled mathematical load accounting

The integrated candidate now expresses wired output load in physical units:
`Vdiff = 0.4 V * serializer.drive`, `Ptermination = Vdiff^2 / 100 ohm`, and
`Irail = 2 mA + Ptermination / (0.35 * Vrail)` while the wired engine is selected.
The voltage, termination, efficiency and bias are explicit configurable
assumptions, not transistor results. The normalized channel still assumes
regulated output swing throughout the accepted rail range. Compliance limits,
output impedance changes and gate-switching charge remain to be modeled.
The last driven level continues to draw termination power until the serializer
is reset/aborted; completing a finite word list does not erase its output state.

RF driver bias is counted only while its oscillator is enabled; wired driver
bias is counted only for the selected wired engine. Shared reference bias
remains active. Oscillator, converter, receiver and digital operating currents
are not yet a complete mode-dependent inventory. Do not interpret the resulting
few-milliampere rail current as a whole-chip current estimate.

The continuous solver integrates ideal-source energy, feed-resistor loss and
load energy. Host charge impulses record the rail capacitor's corresponding
energy decrease. The checked balance is source energy = feed loss + load energy
+ impulse energy + change in rail capacitor energy. This verifies the modeled
lumped rail's accounting, not transistor efficiency or a package power network.
The one lumped rail remains a coupling fixture; it does not replace the separate
physical supply-domain allocations above.
