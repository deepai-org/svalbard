"""Regenerate a wired/reference family with the stress-safe drop-in network.

Usage: stress_safe_wired_layout.py <family> <empty work dir> <drop-in network dir> [usbfix]
Mirrors the base and attachment steps of reference/transmit/receive_integrated.py;
publication screens are not run here. The rail shunt is not placed (no space).
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from design import PROJECT
from layout import generate as base_layout
from wired_protection_layout_ss import generate as connect_primary
family=sys.argv[1]; work=Path(sys.argv[2]); net=Path(sys.argv[3])
# Fits the existing 21 x 26 um placement grid (2 spare slots): one ppolyf_u per leg and
# two FS fast-off devices; the HS mirror reference diode belongs to the bias block.
USB_FIX = dict(termination_geometry_um=(16., 1.3, 1), high_side_fast_off=True, hs_mirror_reference=False)
if len(sys.argv) > 4 and sys.argv[4] == 'usbfix':
    # Opt-in stress-safe USB revision of the RX/USB attachment (wired_receive.build kwargs).
    import functools, wired_receive
    wired_receive.build = functools.partial(wired_receive.build, **USB_FIX)
pdk=PROJECT.parents[1]/'scratch/transceiver-pad-pdk/ngspice'
cfg=json.loads((PROJECT/'spec/schematic-implementation.json').read_text())['io_pad_first_pass']
work.mkdir(parents=True)
params=cfg['generation_parameters'].get(family,{})
base_layout(work/'base',family,external_primary=True,**params)
base=work/'base'
if family=='wired_receive_usb':
    from extract_audit import export_extracted
    from receive_pad_layout import generate as attach_discharge
    import shutil
    export_extracted(base/'pad_wired_receive_usb_flat.ext',base/'physical.spice',capacitance=True)
    inputs=work/'discharge-inputs';inputs.mkdir()
    for s,n in [('pad_wired_receive_usb_flat.gds','wired-receive-usb.gds'),('layout-report.json','wired-receive-usb-layout.json'),('physical.spice','wired-receive-usb-extracted-c.spice')]:
        shutil.copyfile(base/s,inputs/n)
    attach_discharge(work/'discharge',inputs,PROJECT/'analog/pads/generated/receiver-core-discharge')
    staged=work/'primary-inputs';staged.mkdir()
    for s,n in [('combined.gds','rx_pad_with_discharge.gds'),('layout-report.json','layout-report.json'),('physical.spice','pad_wired_receive_usb.spice')]:
        shutil.copyfile(work/'discharge'/s,staged/n)
    base=staged
connect_primary(work/'pad',base,net,cfg['primary_placement_um'][family],pdk)
print(json.dumps(json.loads((work/'pad/layout-screen.json').read_text()),indent=1)[:1500])
