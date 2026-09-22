"""Public connected receiver-detection variant with driver supply loading.

Management, ownership, release/rearm and current-driven shared-rail effects are
included. Supply-to-stimulus/sensor and oscillator sensitivities are explicit
constructor parameters; zero remains a useful uncoupled control. All physical
parameters are assumptions. The declared load envelope is required: small board
coupling capacitors can produce a false absent decision.
"""
from receiver_detect_supply import SupplyDetectChip as ReceiverDetectChip

__all__=['ReceiverDetectChip']
