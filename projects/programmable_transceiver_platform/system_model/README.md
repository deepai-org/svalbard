# Transceiver mathematical models

Start with the [active model guide](architecture_fast/README.md) for commands,
coverage and limitations, and the [project README](../README.md) for what the
platform aims to enable. Current priorities live in the
[risk list](../spec/risk-priorities.md); formal gates live in the
[closure inventory](../spec/mathematical-closure.json).

`architecture_fast/behavioral.py` is the active whole-chip architecture loop.
The more detailed `verification/full_chip_model.py:make_chip` composition
(`exclusive-coupled-domains-host-v1`) remains a supporting coupled model.
They represent the same intended chip at different levels of abstraction;
neither has established full mathematical or physical closure.

`architecture_fast` and `connected` contain shared implementation layers.
Earlier connected compositions remain imported by current runners; age alone
is not a reason to delete a module. Protocol names identify external fixtures,
while chip settings select generic resources and compatible operating values.
