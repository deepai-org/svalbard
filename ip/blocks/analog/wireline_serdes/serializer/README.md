# Half-rate serializer

This directory contains the physical core of a differential 2:1 half-rate
serializer. Complementary clock phases steer one shared tail between matched
EVEN and ODD NMOS differential pairs. Local polysilicon loads produce the
differential signal that directly drives the large nonlinear input-gate load
of `serdes_tx`; the qualification bench does not replace that consumer with a
lumped capacitor.

The generated 48 by 55 um layout is mirror symmetric, uses an
`E_P/O_P/O_N/E_N` equal-centroid data array, puts both loads directly above the
output drains, places both clock selectors and the tail immediately below the
data array, and includes distributed substrate contacts and a contacted guard
ring. The checked physical result has zero Magic DRC errors, one unique
pin-resolved Netgen LVS match, and a 267-resistor/85-capacitor full-RC
extraction.

At the diagnostic 1.25 GBd rate, 36/45 extracted bias cases pass and a
realizable setting exists in all five process/passive/supply/temperature
environments. Selected settings produce at least +/-0.72 V at the serializer
boundary, no more than 56.92 ps serializer-to-TX delay, and 0.774--1.334 mA
serializer current. The harder 2.5 GT/s stress also closes 5/5 environments
after widening the tail-bias search: 21/45 cases pass, with selected settings
from 0.9 to 1.5 V, at least +/-0.60 V serializer swing, at most 50.77 ps delay,
and at most 2.006 mA serializer current. These are public-model pre-silicon
claims, not PCIe compliance evidence.

Run `./run_schematic.sh` for the bounded schematic/load sweep and
`./run_physical.sh` for layout generation, DRC, LVS, PEX, and both extracted
rate matrices. The present bench serializes a static differential `1/0`
parallel word into an alternating stream. Changing parallel words, setup/hold,
clock jitter, mismatch, a realizable bias DAC, routed serializer-to-TX parent,
and full-lane PRBS remain open boundaries.
