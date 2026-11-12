# Evidence status (PD48c, 2026-11-12)

Published cell = PD47 (d2 extra up-diode row present; restored by PD48c after the PD48 no-d2 build).
Current: combined.gds, physical.spice, *-lvs, layout-screen, independent-device-audit, model-audit, pad_wirepad-kldrc.json,
placement-layout.json, lu.json (PD46 LU audit of this GDS), pd47-usb-ls-miller.json (LS/FS/HS/term/pad C/2 kV HBM on this netlist).
pd28-family-sims.json, pd28-usb-ls.json: PD28 cell, historical (superseded by pd47-usb-ls-miller.json).
1 kV HBM and CDM-speed surrogate on this cell: ../pd48-esd-tiering.json `pd48c`.
Superseded: the PD48 no-d2 build (backup scratch/pads-pd48/backup-published/wired-receive-usb-pd48-nod2) and lu-pd48.json.
