# Required treatment of unknowns

User requirement: assume adverse behavior in both directions and ensure the full companion can tolerate it. This applies to analog performance, host timing, power, package, models and numerical results. A favorable nominal case is insufficient.

For each uncertain quantity, distinguish physical lower/upper bounds from selected stress points. Challenge both extremes, adverse correlated combinations and interior resonances/non-monotonic behavior. Tolerance may come from design margin, isolation, verified trim range or another design choice that retains the full required capability. Narrow temperature/voltage operation is allowed, but the actual controlled window, self-heating and ripple must fit the stated bounds.

If bounds are unknown, do not invent a distribution or call the chosen simulation range worst case. Keep the affected requirement open until evidence establishes a range, physical controls bound it, or a verified architecture makes performance insensitive over the necessary range. Configuration or calibration is only mitigation after its range, resolution and convergence are demonstrated. A fallback that drops a required capability is not full-goal closure.

| Quantity | Current evidence/stress points | Adverse directions and next evidence |
|---|---|---|
| Host loading | Native simulations at 5, 8 and 10 pF; Artix specification provides a die-capacitance maximum, not a complete board load | Small loads can worsen ringing; large loads can worsen edge time/current. Establish actual package/PCB bounds and exercise both. |
| Signal-path R/L | Selected 1 ohm, 1/2 nH signal-path cases | Low damping and high loss/delay both matter. Sweep correlated clock/data mismatch and interior resonances after package selection. |
| Output-rail R/L | Zero versus selected 0.25 ohm/2 nH startup isolation; long shared-rail simulations incomplete | Low damping and large drop/bounce both matter. Capture the unresolved numerical behavior before treating any rail sweep as evidence. |
| Process/mismatch | Native typical runs and limited earlier SS experiments | Fast/high-current and slow/low-drive behavior both matter even at controlled temperature/voltage. Bound process/mismatch and calibration coverage. |
| Operating window | Narrow range accepted; numerical temperature and voltage limits not frozen | Low/high voltage, cold/hot junction and local ripple/self-heating must be included. Select feasible limits from evidence. |
| Numerical error | Default and Gear full-interval runs incomplete; four short default-integration diagnostics complete | Artificial damping can conceal instability; numerical ringing can invent it. Require trace inspection and convergence/cross-check evidence. |

None of these selected stress sets constitutes a proven complete uncertainty envelope. This policy does not expand the required environmental range; it requires honest closure within the range eventually specified for the full chip.
