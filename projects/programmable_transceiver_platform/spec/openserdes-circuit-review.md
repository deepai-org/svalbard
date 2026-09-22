# OpenSERDES circuit-level review

Inspected SparcLab/OpenSERDES commit a0b98f0d9fd9937a479d5e39a194a26b8d6dfb14
on2026-09-20. Local read-only reference checkout:/tmp/svalbard-openserdes-review.
No third-party circuit imported or simulated. Repository license GPL-3.0.

## Useful actual circuitry

Resistive_FB_inverter/Resist_FB_INV.src.net exposes a CMOS inverter with three
parallel5um NMOS and six parallel5um PMOS, nominal0.15um lengths. Feedback uses
two series diode-connected long-channel PMOS (W0.55,L8 in the netlist's units),
not a literal linear resistor. This is relevant to compact biasing of a sensitive
inverter, but its asymmetric nonlinear leakage/conduction cannot be equated to
our100kohm feedback. Body ties are to VDD. Recreate and measure its signed I–V,
bias equilibrium, small-signal impedance and loaded dynamics with GF180 devices
before considering substitution. Do not assume dimensions transfer across PDKs.
The accompanying PDF shows700mVpp input and1.8Vpp output; this does not qualify
our roughly190mVpp LO input or establish a frequency/bandwidth result.

## Critical clock-recovery evidence limit

OverSampling_CDR/README.pdf describes external-reference oversampling, multiple
samplers, FIFO/decision logic and boundary detection. Its maximum-frequency field
is blank. The results plot is labeled CDR clk(50kHz). PLL-based MM-CDR is listed
as future work. CLK_RECOVERY.lvs.v exposes CLK_IN, not an independently qualified
autonomous high-speed oscillator. Consequently the published2Gb/s link simulation
must not be attributed to this uploaded CDR without tracing its exact test setup.
The repository also contains Receiver_Bypassing_CDR, making this distinction
particularly important; its existence alone does not prove which path the paper
used. Current review does not resolve the paper-to-artifact correspondence.

## Reproduction issues

The .sp files begin with empty primitive subcircuits. The schematic CDL includes
$PDK_HOME/LVS/Calibre/source.cdl and nshort/pshort models with tool-specific
parameters. These are not standalone ngspice-ready open-PDK simulations without
mapping/dependency work. GDS/netlist availability is not runnable qualification.

Decision: retain as a circuit and architectural reference, downgrade any inference
of a ready2Gb/s recovered-clock implementation. No replacement for our wired
CDR verification or RF LO experiment. Potential follow-up is a small GF180
signed-I–V test of nonlinear feedback, only if current linear-feedback diagnosis
provides a reason to try it; do not blindly replace our self-bias resistor.

Sources:
- https://github.com/SparcLab/OpenSERDES/tree/a0b98f0d9fd9937a479d5e39a194a26b8d6dfb14/Resistive_FB_inverter
- https://github.com/SparcLab/OpenSERDES/blob/a0b98f0d9fd9937a479d5e39a194a26b8d6dfb14/OverSampling_CDR/README.pdf
- https://github.com/SparcLab/OpenSERDES/blob/a0b98f0d9fd9937a479d5e39a194a26b8d6dfb14/OverSampling_CDR/CLK_RECOVERY.lvs.v
