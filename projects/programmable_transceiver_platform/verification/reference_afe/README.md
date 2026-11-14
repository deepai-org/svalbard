# Reference AFE reverse analysis

Scripts that reconstruct a published, fabricated GF180 analog front end (amplifier and SAR ADC) from its open
layout and compare circuit replays with its published measurements. The purpose was to find out which device and
parasitic parameters the measurements constrain.

Status: paused. The published measurements do not uniquely identify device or parasitic parameters, and the
replays did not jointly reproduce the measured amplifier and ADC performance. Nothing here is used as evidence
for the transceiver; ground-truth numbers and their confidence are in `spec/design-assumptions.md`.

| Scripts | Subject |
| --- | --- |
| `amplifier_*.py`, `preamp_*.py` | Amplifier reconstruction and constraints |
| `comparator_*.py`, `controller_*.py`, `register_sim.py`, `pulsegen_*.py`, `sar_transfer.py` | SAR comparator, controller and conversion sequence |
| `cap_*.py`, `fringe_screen.py`, `ratio_screen.py`, `device_geometry.py` | Capacitor array geometry and ratios |
| `reference_*.py`, `bootstrap_sim.py` | Reference drivers, switched charge, sampling switch |
| `pad_*.py`, `physical_constraints.py` | Pad loading and physical constraints |
| `measurement_audit.py`, `transfer_ambiguity.py`, `figure7_screen.py`, `converter_screen.py`, `analyze.py` | Audit of the published measurements and what they can identify |

Stored reports are `evidence/reference-afe-*.json`.
