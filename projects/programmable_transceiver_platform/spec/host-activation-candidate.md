# Experimental streaming host activation

`HostActivationChip` adds a counted activation monitor to the coarse-retuning
candidate. It does not replace the main candidate or the SPI-only capture path.
The startup-quality evidence uses a 0.35 RF filter fraction at 300 kHz; the global
default remains unchanged until combined qualification is complete.

`host_train_start` arms monitoring at an idle, active-clock frame boundary. The
first host edge must arrive within 20 us. The monitor accepts 64 consecutive
valid empty frames (4096 words), using the existing protected metadata/sequence
format. Unallocated slots may carry switching patterns but cannot deliver data.
Every frame must contain 256–512 counted transitions including the forwarded
clock. This is a provisional activity band motivated by the tested pattern, not
a calibrated measure of current, temperature or oscillator readiness.

Training rejects payload allocation, commands, malformed framing, wrong epoch,
duplicate arm and clock gaps. The mathematical per-edge timing window is ±1%;
its physical implementation is not established. A real design must replace or
justify that observation with realizable counters/clock monitors and bounded
latency. Do not interpret ideal test timestamps as a fabricated TDC.

Until qualified, RF descriptors, RF scheduling/capture and wired TX admission/
scheduling reject. During training, the monitor and the actual receiver both
process the words, so valid training exercises real modeled host supply draws.
Missing-clock timeout and reference loss quiesce the candidate and invalidate
activation. Drain acknowledgement alone does not restore it. Status exposes
idle/training/ready/failed and the word count. No package terminals are added.

A new start requires activity within the preceding 64 word periods. Incoming
valid traffic refreshes this age. The chosen age and per-frame activity bounds
still require comparison against analog settling/noise and the supported host
pause contract. This candidate does not yet establish all long-idle, arbitrary
payload-transition or restart behaviors, and is not a universal warm-link proof.

The matched diagnostic fixture uses a direct application of the management arm
at the prelude boundary, then 64 empty frames ending at the measured burst.
Separate tests exercise serialized arm, partial training, exact timeout and
reference loss. Ordinary SPI-only operation must remain available in the final
unified chip; this experimental streaming policy is not permission to remove it.

Required before promotion: both-mode independent TX and RX quality, normal and
cold activation, idle/pause/restart and stale-command behavior, controller/resource
integration, broader phase/noise/activity patterns, and an implementable timing
monitor. TX reconstruction images and output-stage modeling remain independent
open analog obligations.
