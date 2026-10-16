"""Current/headroom screen for the full extracted TX network.

The aligned main/post setting stresses one output with the maximum combined
current. This DC measurement supplements, not replaces, switching lifecycles.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from circuits import wired_transmit
from design import PROJECT
from screen import header,control,run_spice


def screen(work,pdk,physical,calibration_dir,calibration_report=None):
    work.mkdir(parents=True,exist_ok=False)
    architecture=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    tx=architecture['blocks']['wiredtx']['parameters'];circuit=wired_transmit()
    configurations={'main_nominal':{'MAIN':tx['tail_current_a']},
        'main_post_maximum_aligned':{'MAIN':max(tx['current_range_a']),
                                    'POST':max(tx['current_range_a'])*max(tx['postcursor_fraction'])},
        'tmds':{'TMDS':architecture['blocks']['tmds']['parameters']['sink_current_a']}}
    sources=[Path(__file__),Path(__file__).with_name('circuits.py'),Path(__file__).with_name('screen.py'),
             PROJECT/'spec/analog-architecture.json',physical,pdk/'design.ngspice',pdk/'sm141064.ngspice',pdk/'sm141064.spice']
    calibration_report=calibration_report or calibration_dir/'screen-report.json'
    calibration=json.loads(calibration_report.read_text())
    if hashlib.sha256(physical.read_bytes()).hexdigest() not in calibration['sources_sha256'].values():
        raise ValueError('Compliance calibration is not bound to this physical circuit')
    for path,digest in calibration['sources_sha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('Stale compliance calibration')
    sources.append(calibration_report)
    curves={}
    for branch in ('MAIN','POST','TMDS'):
        path=calibration_dir/('dc_'+branch.lower()+'.dat');curves[branch]=np.loadtxt(path,skiprows=1);sources.append(path)
    results={}
    for name,targets in configurations.items():
        settings={'CASCODE':3.3,'DETECT_PBIAS':3.3,'TERM_VCM':1.8};programmed={}
        for branch,target in targets.items():
            rows=curves[branch];index=int(np.argmin(abs(-rows[:,1]-target)))
            settings[branch+'_BIAS']=float(rows[index,0]);settings[branch+'_P']=3.3
            programmed[branch]=dict(target_a=target,bias_v=settings[branch+'_BIAS'],calibration_current_a=float(-rows[index,1]))
        base=header(circuit,pdk,physical)+'VDD VDD 0 3.3\n'
        for port in circuit.ports[4:]:base+=f'V{port} {port} 0 {settings.get(port,0)}\n'
        sweep=base+'VP PAD_P 0 .2\nVN PAD_N 0 3.3\n'
        sweep+=control(work,name,'dc VP .2 3.3 .025','i(VP) i(VN)')
        rows=run_spice(work,name,sweep);current=-rows[:,1];target=sum(targets.values())
        reached=np.flatnonzero(current>=.95*target)
        # Require the threshold to remain met at every higher sampled voltage.
        valid=[i for i in reached if np.all(current[i:]>=.95*target)]
        load=tx['source_r_ohm_per_leg']
        loaded=base+f'VPULL PULL 0 3.3\nRP PULL PAD_P {load}\nRN PULL PAD_N {load}\n'
        label=name+'_loaded';loaded+=control(work,label,'op','v(PAD_P) v(PAD_N) i(VPULL)')
        op=np.atleast_2d(run_spice(work,label,loaded))[0]
        actual=(3.3-op[1])/load
        results[name]=dict(programmed=programmed,total_target_current_a=target,
            minimum_sampled_pad_voltage_for_95_percent_current_v=float(rows[valid[0],0]) if valid else None,
            pad_voltage_v=rows[:,0].tolist(),sink_current_a=current.tolist(),
            loaded_pad_p_v=float(op[1]),loaded_pad_n_v=float(op[2]),loaded_pad_p_current_a=float(actual),
            loaded_current_error_fraction=float(actual/target-1),
            loaded_current_within_3_percent=bool(abs(actual/target-1)<.03))
    report=dict(status='extracted_full_branch_DC_current_compliance_screen',cases=results,
        assumptions=dict(supply_v=3.3,pullup_v=3.3,pullup_ohm_per_leg=tx['source_r_ohm_per_leg'],
            current_threshold_fraction=.95,calibration_acceptance_fraction=.03),
        limitations=['Same physical pad in every case, all inactive branches retained; termination disabled.',
            'Maximum main and postcursor steer to the same leg to expose combined-current headroom demand.',
            'Threshold is a sampled DC engineering measure, not a guaranteed operating limit or eye result.',
            'Ideal bias/control supplies; extracted capacitance but no distributed metal resistance, package return, mismatch or temperature variation.'],
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (work/'wired-transmit-compliance.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:{n:v for n,v in r.items() if n not in ('pad_voltage_v','sink_current_a')} for k,r in results.items()},indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--pdk-model-dir',type=Path,required=True);p.add_argument('--physical',type=Path,required=True);p.add_argument('--calibration-dir',type=Path,required=True)
    a=p.parse_args();screen(a.output_dir.resolve(),a.pdk_model_dir.resolve(),a.physical.resolve(),a.calibration_dir.resolve())
