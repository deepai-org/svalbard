# Clock ownership and sustained-rate obligations

**Current operating decision:** RF and wired payload operation are mutually exclusive on the same chip. Both capabilities remain required; additional physical resource sharing is encouraged. See the [exclusive-engine policy](exclusive-engine-policy.md), which supersedes simultaneous-operation requirements below. Model/RTL enforcement and resource rebudgeting remain implementation work.

The pin plan provides REF_IN, chip-forwarded D2H_CLK and FPGA-forwarded H2D_CLK.
RF and wired synthesis/recovery are independent engines sharing a reference and
control infrastructure. A forwarded host clock establishes capture timing; it
does not by itself make the host's payload production match a DAC or serializer.

| Boundary | Current intended owner | Required rate relationship |
| --- | --- | --- |
| Wired RX samples | Transition-driven CDR | Host consumes recovered data with bounded service gaps; host transport capacity exceeds incoming rate |
| RF ADC samples | Local sample-clock generation | D2H queues absorb bounded scheduling/CDC delay, not unlimited host stalls |
| Wired TX bits | Local wired TX synthesizer | Host symbol supply must follow that consumption rate, or explicit protocol-aware rate matching must exist externally |
| RF DAC samples | Local sample-clock generation | Host sample supply must follow that consumption rate, or an explicitly specified resampler/flow-control mechanism is required |
| D2H GPIO | Chip forwarded clock | Aggregate reserved slots must meet actual RX production rates |
| H2D GPIO | FPGA forwarded clock | Transport word rate may differ from payload rate; counts/padding permit unused slots but do not provide consumer feedback |

The current v2 metadata carries counts, sequence and limited commands, not
consumer credits or timestamps. Do not assume unallocated control bandwidth,
extra pins, arbitrary raw-bit insertion/deletion, or an implicit sample-rate
converter. The top coexistence mode has no spare scheduled payload slot.

For a constant payload rate error Δr, queue occupancy changes by Δr*t. A finite
queue or larger startup prefill cannot solve nonzero persistent mismatch.
Next choose and simulate an explicit sustainable mechanism: common-reference
payload pacing where its frequency relationships can be guaranteed, or accounted
feedback/status that controls external production. Quantify clock tolerances,
feedback latency and FIFO bounds before selecting the mechanism. Preserve both RF and wired capabilities in exclusive modes, with independently recovered wired RX timing where needed.

The connected model currently assumes source-matched TX consumption rates.
Its signed wired oscillator tests concern initial CDR error, not persistent
host/DAC mismatch. This obligation is open, not solved by those passing tests.

## Baseline candidate selected for mathematical implementation

Use chip-forwarded D2H word edges as the FPGA's payload-pacing reference. External
FPGA rational accumulators generate TX word/sample enables, independently of
payload bit values. At the lower profile generate wired words at1/2 and I/Q pairs
at4/25 of D2H word rate. At the higher profile use4/5 and8/125. The chip must
synthesize local wired-TX and DAC rates with those same average ratios. Independent
RF/wired oscillators remain; sharing a frequency reference does not mean sharing
one oscillator or recovered wired-RX clock.

This candidate needs no new pins, credits, padding data or raw-stream edits.
The host may use a separate H2D service clock, but its sample generation must
follow D2H pacing and its queues/CDC must meet service bounds. Current connected
implementation uses a common ideal host tick; separate H2D-clock verification is
still open. Host wrappers and actual chip clock synthesis must implement the
ratios before this is a hardware claim. A mode with intentionally independent
sample frequency, spread-spectrum TX or lost reference needs a separately
specified tracking mechanism/failure response; do not silently apply this model.

The pacing implementation verifies less than one sample of cumulative phase
quantization and exact counts over each denominator-length period. It removes
persistent rate error only under the stated common-reference clock-ratio premise.

## Separate host service-clock experiment

The connected model now schedules D2H reference edges and H2D service edges as
separate rational-time events. Host payload enables still count D2H edges; H2D
frames use their own word index, frequency and phase. Eight complete-path cases
cover both modes, H2D±100ppm and0/one-third-reference-tick phase. Finite delivery,
TX consumption and RF-command timing pass. This is a queue-level CDC abstraction:
reference-domain items become visible at the next service event without a modeled
synchronizer delay. Physical CDC latency/metastability and prolonged host stalls
remain open; exact analog/reference ratios are still assumed.

## Recovered raw-stream timing information

The recovered-clock path cannot promise unlimited transition-free payloads. In
current noiseless adapter tests,327680 constant bits corrupt later changing data,
while equally long randomized payloads with maximum runs5 or64bits preserve all
words at both line rates and both tested initial offset signs. These tests do not
establish a safe run limit or validate protocol encoding.

Make transition density an external encoding/application obligation for recovered
raw-stream mode. The chip must not silently insert transition bits into supplied
raw payloads or consume unbudgeted coding bandwidth. Protocol-specific validation
must use actual legal symbols and account for training, idle, fault and recovery
behavior. Separately referenced sampling, if offered, needs its own explicit
phase/frequency requirements; it is not a universal substitute for CDR.

## Integer-reference candidate (pass 831)

The connected IntegerClockChip candidate uses the existing40MHz reference divided
by four for the wired PLL. Feedback counts125 and250 provide1.25GHz and2.5GHz;
the RF synthesizer retains40MHz comparison and count60 for2.4GHz. This avoids
intentional fractional count modulation without extra pins or changed host pacing.
Reference reset counts actual future input edges. Lock thresholds retain their
absolute-time and relative-frequency meaning, with eight slower qualification
observations. Exact divider counts and noisy four-path operation pass, while the
10MHz loop's averaged-detector approximation and physical divider/noise behavior
remain limitations. Historical40MHz fractional-ratio reports remain separate.
