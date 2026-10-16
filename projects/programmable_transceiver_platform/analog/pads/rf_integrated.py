"""Rebuild the complete connected RF pad model and layout with retained-state screens.

First-pass construction evidence, not ESD, core-survival or RF qualification.
Both directions use one physical protection network and shared RF parameters.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from protection_pad import generate
from protected_rf_route import run as route_screen
from analog_screen import screen
from design import PROJECT


def run(work, generated, pdk):
    work.mkdir(parents=True,exist_ok=False)
    pad=work/'pad'
    generate(pad,generated,wide_signals=True,escape_width_um=24.)
    routed=work/'routed'
    route_screen(routed,generated,pdk,pad)
    architecture=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    gain=architecture['blocks']['rfdriver']['parameters']['gain_range'][1]
    maximum=work/'maximum-gain';maximum.mkdir()
    (maximum/'.spiceinit').write_text('set ngbehavior=hs\n')
    before=Path.cwd()
    try:
        os.chdir(maximum)
        screen(maximum,pdk,routed/'physical.spice','rf_transmit',
            route_report=routed/'route-resistance.json',capacitance_location='core',
            resistance_corner='high_resistance',rf_tx_gain=gain)
    finally:os.chdir(before)
    pulse=work/'pulses'
    subprocess.run([sys.executable,str(Path(__file__).with_name('protection_pulse.py')),
        '--fixture',str(routed/'rf_transmit/lifecycle.spice'),
        '--physical',str(routed/'rf_transmit/segmented-pad.spice'),
        '--output-dir',str(pulse)],check=True)
    layout=json.loads((pad/'pad-layout.json').read_text())
    route=json.loads((routed/'route-screen.json').read_text())
    high=json.loads((maximum/'screen-report.json').read_text())
    pulses=json.loads((pulse/'pulse-screen.json').read_text())
    if not (route['all_screens_complete'] and high['transient_complete']
            and all(v['transient_complete'] for v in pulses['cases'].values())):
        raise ValueError('Incomplete integrated RF simulation')
    reports=[pad/'pad-layout.json',pad/'independent-device-audit.json',routed/'route-screen.json',
             maximum/'screen-report.json',pulse/'pulse-screen.json']
    result=dict(status='integrated_RF_first_pass_built_not_protection_qualified',
        construction_checks_complete=True,area_fits=layout['fits_assigned_area'],
        physical_model=str(routed/'physical.spice'),gds=str(pad/'pad.gds'),
        family_screens={name:str(routed/name/'screen-report.json') for name in ('rf_receive','rf_transmit')},
        nominal_gain_high_resistance_power_dbm=route['results']['rf_transmit']['tx_load_power']['windows']['active']['fundamental_power_dbm'],
        maximum_gain_high_resistance_power_dbm=high['tx_load_power']['windows']['active']['fundamental_power_dbm'],
        core_pulse_extrema={name:pulses['cases'][name]['windows']['pulse']['core_p_to_local_return_v']
                           for name in ('positive_100mA','negative_100mA')},
        limitations=['Core protection coordination and current capacity unresolved.',
                     'Behavioral RF core boundaries; routing loss is a sheet-resistance approximation.',
                     'Provider assembly is a separate mandatory integration check before publication.'],
        report_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in reports},
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__),PROJECT/'spec/analog-architecture.json',PROJECT/'spec/contract.json')})
    (work/'integrated-screen.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output-dir','generated','pdk-model-dir'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.output_dir.resolve(),a.generated.resolve(),a.pdk_model_dir.resolve())
