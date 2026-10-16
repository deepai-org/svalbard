"""Admittance of the complete existing wired TX pad, with every branch retained.

Independent operating points supplement the retained-charge lifecycle. They do
not establish protocol compliance, transient protection or a new pad variant.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from circuits import wired_transmit
from design import PROJECT
from loading_audit import anchor_floating_conductors
from screen import header,control,run_spice


def screen(work,pdk,physical,calibration_report=None):
    work.mkdir(parents=True,exist_ok=False)
    circuit=wired_transmit()
    spec=PROJECT/'spec/schematic-implementation.json'
    if calibration_report is None:
        cfg=json.loads(spec.read_text())['io_pad_first_pass']['tx_integration_fixture']
        currents={name:dict(bias_v=value) for name,value in cfg['bias_v'].items()}
        bias_source=spec
        bias_scope='Selected shared lifecycle biases; not independent DC recalibration.'
    else:
        calibration=json.loads(calibration_report.read_text())
        for path,digest in calibration['sources_sha256'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:
                raise ValueError('Stale TX calibration source: '+path)
        if not calibration['physical_capacitance_included'] or hashlib.sha256(physical.read_bytes()).hexdigest() not in calibration['sources_sha256'].values():
            raise ValueError('TX calibration is not bound to this extracted circuit')
        currents=calibration['calibration'];bias_source=calibration_report
        bias_scope='Separate DC calibration; not loaded lifecycle biases.'
    model,anchors=anchor_floating_conductors(header(circuit,pdk,physical),1e12)
    baseline={'CASCODE':3.3,'DETECT_PBIAS':3.3,'TERM_VCM':1.8}
    configurations={
        'disabled':(3.3,1.8,{}),
        'reset':(3.3,1.8,{'CASCODE':0}),
        'unpowered_external_peer':(0,1.8,{'CASCODE':0,'DETECT_PBIAS':0,'TERM_VCM':0}),
        'source_termination':(3.3,1.8,{'TERM_ENABLE':3.3}),
        'main':(3.3,1.8,{'MAIN_P':3.3,'MAIN_BIAS':currents['MAIN']['bias_v']}),
        'main_post':(3.3,1.8,{'MAIN_P':3.3,'MAIN_BIAS':currents['MAIN']['bias_v'],
                                    'POST_N':3.3,'POST_BIAS':currents['POST']['bias_v']}),
        'main_post_terminated':(3.3,1.8,{'TERM_ENABLE':3.3,'MAIN_P':3.3,'MAIN_BIAS':currents['MAIN']['bias_v'],
                                    'POST_N':3.3,'POST_BIAS':currents['POST']['bias_v']}),
        'tmds':(3.3,3.,{'TMDS_P':3.3,'TMDS_BIAS':currents['TMDS']['bias_v']}),
        'detection':(3.3,.4,{'DETECT_ENABLE':3.3,'DETECT_PBIAS':currents['DETECT']['bias_v']}),
    }
    cases={}
    for name,(supply,common,settings) in configurations.items():
        values={**baseline,**settings}
        base=model+f'VDD VDD 0 {supply}\n'
        for port in circuit.ports[4:]:base+=f'V{port} {port} 0 {values.get(port,0)}\n'
        cases[name]=dict(supply_v=supply,pad_common_mode_v=common,controls=values,modes={})
        for mode,negative_amplitude in [('odd',-.5),('common',.5)]:
            deck=base+f'VP PAD_P 0 DC {common} AC .5\nVN PAD_N 0 DC {common} AC {negative_amplitude}\n'
            vectors='real(i(VP)) imag(i(VP)) real(i(VN)) imag(i(VN))'
            label=name+'_'+mode
            command=control(work,label,'ac dec 20 100Meg 10G',vectors).replace('.control\n','.control\nset numdgt=15\n',1)
            rows=np.atleast_2d(run_spice(work,label,deck+command,reject_transient_op=True))
            if rows.shape[1]!=5 or not np.isfinite(rows).all() or rows[-1,0]<9.999e9:
                raise ValueError('Incomplete TX admittance sweep: '+label)
            frequency=rows[:,0]
            real=-rows[:,[1,3]]/np.array([.5,negative_amplitude])
            imag=-rows[:,[2,4]]/np.array([.5,negative_amplitude])
            capacitance=imag/(2*np.pi*frequency[:,None])
            index=int(np.argmin(abs(frequency-1e9)))
            if abs(frequency[index]/1e9-1)>1e-6:raise ValueError('Missing 1GHz point')
            cases[name]['modes'][mode]=dict(frequency_hz=frequency.tolist(),
                real_admittance_s_per_leg=real.tolist(),imag_admittance_s_per_leg=imag.tolist(),
                effective_capacitance_f_per_leg=capacitance.tolist(),
                at_1ghz=dict(effective_capacitance_f_per_leg=capacitance[index].tolist(),real_admittance_s_per_leg=real[index].tolist()))
    report=dict(status='complete_branch_TX_admittance_screen_not_compliance',cases=cases,
        bias_scope=bias_scope, numerical_floating_conductor_anchors=anchors,
        operating_point_policy='Reject transient operating-point fallback; anchors are numerical only.',
        assigned_budget_f_per_leg=circuit.requirements['electrical_parameters']['capacitance_f_per_leg'],
        limitations=['Same extracted pad in every case; no inactive branch removed and no budget-sized capacitor added.',
            'Ideal pad voltage probes characterize the local port; board/package and distributed wire resistance are absent.',
            'Controls, biases and TERM_VCM are stiff small-signal sources; finite regulator and serializer impedance are not established.',
            'Im(Y)/omega is effective admittance, not a sum of independent physical capacitors. Active configurations can differ by leg.',
            'Independent biased operating points discard stored charge; existing lifecycle and reconfiguration benches remain required.',
            'Small-signal analysis does not establish ESD survival, large-signal distortion or data eye margin.'],
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__),Path(__file__).with_name('circuits.py'),Path(__file__).with_name('design.py'),Path(__file__).with_name('screen.py'),physical,bias_source,Path(__file__).with_name('loading_audit.py'),
             Path(__file__).resolve().parents[2]/'spec/analog-architecture.json',Path(__file__).resolve().parents[2]/'spec/contract.json',pdk/'design.ngspice',pdk/'sm141064.ngspice',pdk/'sm141064.spice']})
    (work/'wired-transmit-loading.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({name:case['modes']['odd']['at_1ghz'] for name,case in cases.items()},indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--pdk-model-dir',type=Path,required=True)
    p.add_argument('--physical',type=Path,required=True)
    p.add_argument('--calibration-report',type=Path)
    a=p.parse_args();screen(a.output_dir.resolve(),a.pdk_model_dir.resolve(),a.physical.resolve(),a.calibration_report.resolve() if a.calibration_report else None)
