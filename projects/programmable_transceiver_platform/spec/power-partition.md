# Power requirement IDs

The power budget, islands, supply grid, decap plan and rails are specified in
[power-delivery.md](power-delivery.md); the numbers come from `spec/budgets/power_budget.py`.
This file only defines the requirement IDs that `performance-requirements.json` traces to it.

| ID | Requirement |
| --- | --- |
| PWR-MODE-CEIL | Total chip current stays within 360 mA in wired and USB modes, 260 mA in RF modes with the external LO and 340 mA in RF modes with the on-chip LO, at worst in-window analog currents, including the 37.5 mA rfdriver board feed. |
| PWR-DIG-WIRED | The digital macro draws at most 60 mA in wired and USB modes, with unused domains clock-gated, signed off with activity-annotated power. |
| PWR-DIG-RF | The digital macro draws at most 40 mA in RF modes, same sign-off. |
| PWR-HOST-RF | RF modes run the host link at div2 (`debug.host_link.rate`). |
| PWR-DROP | Total drop from the source (3.3 V - 1 %) to any block tap is at most 117 mV, so the die stays at or above 3.15 V. |
| PWR-THERM | Junction temperature stays within 22-32 C across the stopped-to-maximum mode step (board requirement B2a). |
