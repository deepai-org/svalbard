# Chain 1 inverter canary

This smoke design is deliberately tiny. It must traverse Xschem netlisting, ngspice simulation, Magic layout loading, DRC, extraction, Netgen LVS, post-layout simulation, and comparison against a checked golden result in the exact pinned ARM64 container.

The schematic uses two GF180 5 V MOS devices sized to match `gf180mcu_fd_sc_mcu7t5v0__inv_1`. The layout stage imports that exact standard-cell view from the pinned candidate PDK into disposable scratch; no installed PDK file is copied into Git.

Passing this canary qualifies only this exact smoke chain. It does not qualify the PDK for fabrication, the tools for PCIe signoff, or any high-speed/electrical claim.
