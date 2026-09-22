"""Common mathematical candidate entry.

Includes autonomous sampled clocks, wired/RF paths, receiver detection, diagnostic
tile and timed management. This remains an incomplete architecture: monitor
qualification, triggers, continuous TX control and physical clock refinement are open.
Acquisition and receiver detection must be requested by callers; this entry does
not silently perform testbench startup or declare physical qualification.
"""
from continuous_receiver import ContinuousChip as ProgrammableChip
