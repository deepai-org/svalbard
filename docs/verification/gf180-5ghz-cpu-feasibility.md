# GF180 native-3.3 V 5 GHz CPU feasibility

## Decision

A genuine 5 GHz synchronous CPU is not a credible all-PVT target on GF180MCU.
The 200 ps cycle fails before useful combinational logic is inserted. A 5 GHz
ring, serial lane phase, or externally presented clock is a different and much
weaker claim than advancing CPU state correctly five billion times per second.

An aggressive tiny bit-serial core should initially target approximately
1 GHz at the declared slow/high-temperature environment. A 1.5--2 GHz typical
demonstrator may be possible with custom native-3.3 V sequential cells and a
very shallow pipeline. These are design targets, not validated limits.

## Sequential timing inequality

For every register-to-register path,

```text
Tcycle >= tCLK->Q + tlogic + tsetup + tclock_uncertainty
```

At 5 GHz, `Tcycle = 1 / 5 GHz = 200 ps`.

The native-3.3 V Avalon `dyn_dfxtp_2` Liberty data was inspected at commit
`c35a86ac394e548c3de37e43a579fd770f1842a6`. Even using its most optimistic
0.5 fF output load and 10 ps clock/data slew table entries gives:

| Environment | CLK-to-Q | Setup | Empty-path total | Empty-path ceiling | Required high + low pulse |
|---|---:|---:|---:|---:|---:|
| FF, -40 C, 3.60 V | 194 ps | 128 ps | 322 ps | 3.10 GHz | 246 ps |
| TT, 25 C, 3.30 V | 244 ps | 171 ps | 415 ps | 2.41 GHz | 330 ps |
| SS, 125 C, 3.00 V | 323 ps | 236 ps | 558 ps | 1.79 GHz | 484 ps |

This is a lower bound on the period, not a signoff result. A real receiving D
pin is about 6 fF in this library, the output slew is not ideal, and logic,
wires, skew, jitter, supply drop, extraction, and statistical margin all add
delay. The 5 GHz target has negative empty-path slack of 122 ps even at FF and
358 ps at SS.

## Independent device-speed bound

The experiment in
`ip/blocks/digital/gf180_cpu_speed_limit` uses the pinned GF180 model and a
minimum native-3.3 V inverter (`L=0.28 um`, `Wn=0.22 um`, `Wp=0.44 um`). Three
identical stages create an FO1 load; a separate unloaded three-stage ring is an
optimistic oscillation bound.

| Environment | Schematic FO1 inverter | Unloaded 3-stage ring |
|---|---:|---:|
| FF, -40 C, 3.63 V | about 29 ps | about 6.2 GHz |
| TT, 25 C, 3.30 V | about 43 ps | about 4.3 GHz |
| SS, 125 C, 2.97 V | about 68 ps | about 2.7 GHz |

Thus a 200 ps cycle contains only 4.7 ideal inverter delays at TT and 2.9 at SS,
before layout. State storage consumes several such delays. The ring result also
shows why a one-corner oscillator screenshot cannot establish CPU feasibility:
even this unloaded schematic ring is below 5 GHz at TT and SS.

## Minimum useful CPU path

Our extracted fast native-3.3 V NAND2 measures 87.93 ps nominal and 143.43 ps at
its worst screened PVT environment under the exact FO1 fixture. Combining only
two such logic levels with the optimistic DFF bound yields:

```text
TT: 415 + 2*87.93  = 591 ps  -> 1.69 GHz before uncertainty
SS: 558 + 2*143.43 = 845 ps  -> 1.18 GHz before uncertainty
```

Two logic levels are already an austere budget for select/decode plus a one-bit
ALU or next-state function. Reserving clock and wiring margin moves the first
credible slow-corner target toward 0.8--1.0 GHz. A full parallel adder, register
file read, or broad instruction decode would require more stages or a lower
clock. Bit-serial arithmetic and a small local register bank are therefore the
right architecture if density and maximum clock are the experiment's goals.

## Why a 10 Gb/s SerDes does not imply a 5 GHz CPU

A 10 Gb/s NRZ lane has a 100 ps unit interval, but its digital core can be
half-rate (5 GHz) or quarter-rate (2.5 GHz). The fastest front-end stages are
shallow, fixed-function, small-swing current-mode circuits; they do not perform
a rail-to-rail register-to-logic-to-register CPU loop each UI. Parallelism moves
most serializer, deserializer, coding, and control logic to the lower clock.

A SerDes result would still need extracted transistor simulation, package and
channel models, jitter/BER analysis, and silicon correlation. It is not evidence
that arbitrary synchronous standard-cell logic can run at the serial bit rate.

## What might still be worth building

1. Characterize a custom native-3.3 V pulsed latch and CML latch across extracted
   PVT, mismatch, clock slew, duty cycle, load, and supply noise.
2. Synthesize a minimal bit-serial core at 0.8, 1.0, 1.25, 1.5, and 2.0 GHz using
   characterized native cells; route it and measure worst path and clock power.
3. Fabricate a canary containing inverter rings, loaded rings, latch chains,
   ripple/carry paths, and the same clock tree used by the core.
4. Treat 5 GHz as a falsification experiment for a tiny CML/dynamic pipeline,
   not as the tapeout requirement. It is acceptable if only a local oscillator
   or serializer phase reaches that rate; label the result precisely.

## Power sanity check

The Avalon dynamic DFF clock pin is about 5.3 fF. Merely charging 200 such ideal
clock-pin capacitors at 5 GHz and 3.3 V is approximately

```text
P = N*C*V^2*f = 200*5.3 fF*(3.3 V)^2*5 GHz = 57.7 mW
```

This excludes clock-tree capacitance, internal short-circuit/switching energy,
logic, memories, and leakage. A tiny footprint therefore does not automatically
make a 5 GHz core thermally easy; current-mode logic would trade some switching
limits for continuous static power.
