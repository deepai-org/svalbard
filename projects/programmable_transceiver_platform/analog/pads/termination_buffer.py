"""Parametric transistor feedback-buffer candidate; not yet integrated or laid out.

The reference and tail bias are explicit core inputs. Output current limiting,
power-off isolation and safe enable are still required before pad integration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from circuits import Circuit, Mos
from design import PROJECT
from screen import run_spice


def build(input_width=20., source_width=320., sink_width=160., first_stage_scale=1., gated=False, complementary_isolation=False, restore_high=False, restore_reference=False):
    if restore_high and restore_reference:raise ValueError("Select one gain restoration topology")
    devices=[]
    def mos(name,nodes,kind,w,l):
        # Finger into the same modest unit widths used by pad layout primitives.
        count=max(1,int(np.ceil(w/20.)))
        for i in range(count):
            devices.append(Mos(f'{name}_{i}',tuple(nodes.split()),kind,w/count,l))
    mos('INPUT_FB','MIR OUT TAIL VSS','nfet_03v3',input_width*first_stage_scale,1.)
    mos('INPUT_REF','GAIN REF TAIL VSS','nfet_03v3',input_width*first_stage_scale,1.)
    mos('MIRROR_REF','MIR MIR VDD VDD','pfet_03v3',40.*first_stage_scale,1.)
    mos('MIRROR_OUT','GAIN MIR VDD VDD','pfet_03v3',40.*first_stage_scale,1.)
    mos('TAIL','TAIL BIAS '+('TAIL_RETURN' if gated else 'VSS')+' VSS','nfet_03v3',10.*first_stage_scale,1.)
    mos('SOURCE',('LOCAL_OUT GAIN TOP VDD' if gated else 'OUT GAIN VDD VDD'),'pfet_03v3',source_width,.5)
    mos('SINK',('LOCAL_OUT GAIN BOTTOM VSS' if gated else 'OUT GAIN VSS VSS'),'nfet_03v3',sink_width,.5)
    ports=['VDD','VSS','REF','BIAS','OUT']
    if gated:
        ports+=['ENABLE']
        mos('EN_INV_P','ENABLE_B ENABLE VDD VDD','pfet_03v3',20.,.28)
        mos('EN_INV_N','ENABLE_B ENABLE VSS VSS','nfet_03v3',10.,.28)
        mos('HEADER','TOP ENABLE_B VDD VDD','pfet_03v3',640.,.28)
        mos('FOOTER','BOTTOM ENABLE VSS VSS','nfet_03v3',320.,.28)
        mos('TAIL_ENABLE','TAIL_RETURN ENABLE VSS VSS','nfet_03v3',100.,.28)
        if restore_reference:
            mos('GAIN_RESTORE_N','GAIN ENABLE_B REF VSS','nfet_03v3',10.,.28)
            mos('GAIN_RESTORE_P','GAIN ENABLE REF VDD','pfet_03v3',20.,.28)
        elif restore_high:
            mos('GAIN_RESTORE','GAIN ENABLE VDD VDD','pfet_03v3',20.,.28)
        else:
            mos('GAIN_RESTORE','GAIN ENABLE_B VSS VSS','nfet_03v3',10.,.28)
        mos('OUTPUT_ISOLATE','LOCAL_OUT ENABLE OUT VSS','nfet_06v0',1200.,.7)
    if complementary_isolation:
        if not gated:raise ValueError('Complementary isolation requires gated buffer')
        from termination_switch_candidate import link
        devices.extend(link('BUFFER_COMPLEMENT','LOCAL_OUT','OUT','ENABLE'))
    return Circuit('termination_buffer_candidate',ports,devices,{},[
        'Complementary second stage has unregulated quiescent current.',
        'Explicit reference/tail bias; no current limit or autonomous supply qualification.',
        'Gated variant adds supply/return switching, gain restoration and NMOS output isolation; safe terminal stress remains unverified.' if gated else 'No enable or power-off isolation.',
        'Compensation and layout remain to be designed; DC convergence is not stability.'])



def screen(work,pdk):
    work.mkdir(parents=True,exist_ok=False)
    c=build();(work/'candidate.spice').write_text(c.spice())
    arch=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    params=arch['blocks']['wiredtx']['parameters']
    load=max(params['current_range_a'])*(1+max(params['postcursor_fraction']))
    deck=('Termination buffer DC feasibility, explicit bias and reference\n'
          f'.include {pdk}/design.ngspice\n.lib {pdk}/sm141064.ngspice typical\n'
          '.temp 27\n'+c.spice()+'\nXBUF VDD 0 REF BIAS OUT termination_buffer_candidate\n'
          'VSUP VDD 0 3.3\nVREF REF 0 1.65\nVBIAS BIAS 0 .9\nILOAD OUT 0 0\n'
          '.control\nset wr_singlescale\nset wr_vecnames\n'
          f'dc ILOAD {-load} {load} {load/24}\n'
          f'wrdata {work}/dc.dat v(OUT) v(GAIN) i(VSUP)\nquit\n.endc\n.end\n')
    # Internal gain node must be addressed hierarchically.
    deck=deck.replace('v(GAIN)','v(xbuf.GAIN)')
    x=run_spice(work,'dc',deck)
    assert x.shape[0]>=48 and np.isfinite(x).all()
    report=dict(status='transistor_buffer_DC_candidate_not_adopted',device_count=len(c.devices),
        load_range_a=[float(x[:,0].min()),float(x[:,0].max())],
        output_range_v=[float(x[:,1].min()),float(x[:,1].max())],
        maximum_target_error_v=float(abs(x[:,1]-1.65).max()),
        supply_draw_range_a=[float((-x[:,3]).min()),float((-x[:,3]).max())],
        wired_tx_current_budget_a=arch['blocks']['wiredtx']['resource_allocation']['current_budget_ma']['wired']*1e-3,
        assumptions=dict(supply_v=3.3,reference_v=1.65,tail_bias_v=.9,temperature_c=27),
        limitations=c.limitations,
        source_sha256={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),PROJECT/'spec/analog-architecture.json',work/'candidate.spice',work/'dc.spice']})
    report['load_steps']={}
    for name,comp in [('uncompensated',''),('compensated','RCOMP GAIN COMP 100\nCCOMP COMP OUT 10p\n')]:
        step=deck.split('.control')[0].replace('ILOAD OUT 0 0',
            f'ILOAD OUT 0 PWL(0 0 20n 0 21n {load} 60n {load} 61n {-load} 100n {-load} 101n 0)\nCLOAD OUT 0 10p')
        step=step.replace('.ends termination_buffer_candidate',comp+'.ends termination_buffer_candidate')
        step+=f'.control\nset wr_singlescale\nset wr_vecnames\ntran .02n 150n\nwrdata {work}/{name}.dat v(OUT) i(VSUP)\nquit\n.endc\n.end\n'
        y=run_spice(work,name,step)
        if not np.isfinite(y).all() or y[-1,0]<149.99e-9:raise ValueError('Incomplete load step')
        windows={}
        for state,a,b in [('source',50,59),('sink',90,99),('recovered',140,150)]:
            z=y[(y[:,0]>=a*1e-9)&(y[:,0]<=b*1e-9),1]
            windows[state]=dict(min_v=float(z.min()),max_v=float(z.max()),peak_to_peak_v=float(np.ptp(z)))
        report['load_steps'][name]=dict(output_min_v=float(y[:,1].min()),output_max_v=float(y[:,1].max()),windows=windows,
            scope='Standalone 10pF load; ideal 100ohm/10pF series Miller compensation when selected. No stability margin or retained-pad lifecycle claim.')
        f=work/(name+'.spice');report['source_sha256'][str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
    report['decision']='Keep as transistor starting point only. Uncompensated loop rings; tested compensation leaves large loaded error at the sampled deadlines. Resolve loop bandwidth and stability before integration.'
    (work/'screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--pdk-model-dir',type=Path,required=True)
    a=p.parse_args();screen(a.output_dir.resolve(),a.pdk_model_dir.resolve())
