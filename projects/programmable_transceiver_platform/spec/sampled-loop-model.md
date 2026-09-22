# Sampled phase-detector mathematical contract

The detector samples phase error in reference cycles at each comparison edge and
holds it until the next edge. The PI integral state and oscillator phase continue
to evolve. Reference loss freezes the held tuning voltage; detector ticks continue
to advance as bookkeeping, without updating the held measurement.

For the unsaturated noiseless local model, let g=Kvco/N, T=1/fref, e be phase error,
and i be integral voltage relative to its equilibrium. The exact update is

    [e_next]   [1-g*Kp*T-g*Ki*T*T/2   -g*T] [e]
    [i_next] = [Ki*T                       1] [i]

The test computes this recurrence independently and compares both states against
the continuous integration. Eigenvalue magnitude below one establishes local
stability for these assumptions. Saturation, startup, loss/recovery and noise are
checked separately in the nonlinear model; the recurrence does not prove them.

At the declared gains,1MHz natural frequency is locally stable at both10MHz and
40MHz comparison. The3MHz/10MHz negative case is unstable. These values are assumed
loop parameters, not measured bandwidths. This detector is a sampled/held average
model; physical charge-pump pulses, compliance, dead zones, propagation delays and
extra loop-filter poles are not included. Those effects must be represented or
bounded before using this result as evidence for a transistor implementation.
