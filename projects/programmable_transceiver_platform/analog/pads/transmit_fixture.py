"""Compose the selected extracted TX pad, buffer and interlock reproducibly.

External network and prototype core bias components remain present in every
state. The sequencer supplies requests; controls here start disabled. Macro
layouts are separate: this does not claim combined core placement or routing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from design import PROJECT


def build(output, pdk, pad_override=None, bias_override=None, bias_resistance_ohm=None):
    spec=PROJECT/'spec/schematic-implementation.json'
    arch=PROJECT/'spec/analog-architecture.json'
    cfg=json.loads(spec.read_text())['io_pad_first_pass']['tx_integration_fixture']
    a=json.loads(arch.read_text())
    if bias_override:
        if set(bias_override)-set(cfg['bias_v']):raise ValueError('Unknown bias override')
        cfg['bias_v'].update(bias_override)
    models={name:PROJECT/path for name,path in cfg['models'].items()}
    if pad_override is not None: models['pad']=pad_override.resolve()
    expected={'pad':['PAD_P','PAD_N','VDD','VSS','CASCODE','MAIN_P','MAIN_N','MAIN_BIAS','POST_P','POST_N','POST_BIAS','TMDS_P','TMDS_N','TMDS_BIAS','DETECT_ENABLE','DETECT_PBIAS','TERM_ENABLE','TERM_VCM'],
              'buffer':['VDD','VSS','REF','BIAS','OUT','ENABLE'],
              'interlock':['VDD','VSS','REQ_MAIN','REQ_POST','REQ_TMDS','REQ_DETECT','REQ_TERM','RESET','QUALIFIED','SUPPLY_OK','CONFLICT','VALID','EN_MAIN','EN_POST','EN_TMDS','EN_DETECT','EN_TERM']}
    cells={};texts=[]
    for name,path in models.items():
        text=path.read_text();joined=re.sub(r'\n\+\s*',' ',text)
        definition=next(line.split() for line in joined.splitlines() if line.startswith('.subckt '))
        if definition[2:]!=expected[name]:raise ValueError('Selected '+name+' interface changed')
        cells[name]=definition[1]
        texts.append('\n'.join(line for line in text.splitlines() if not line.startswith(('.lib ','.include '))))
    if bias_resistance_ohm is not None and not 0<bias_resistance_ohm<=10000:
        raise ValueError('Bias resistance must be positive and bounded')
    v=2*a['blocks']['bias']['parameters']['common_mode_v']
    low,high=a['blocks']['monitor']['parameters']['supply_window_v']
    period=cfg['data_period_s'];edge=cfg['data_edge_s']
    if not 0<edge<period/2:raise ValueError('Invalid serializer edge allocation')
    lines=['Selected integrated TX retained-network fixture',f'.include {pdk}/design.ngspice']
    lines += [f'.lib {pdk}/sm141064.ngspice {corner}' for corner in ['typical','res_typical','diode_typical','mimcap_typical']]
    lines += ['.temp 27',*texts,'Xpad '+' '.join(expected['pad'])+' '+cells['pad'],'VSS VSS 0 0',
              f'RDIFF_LOAD BOARD_P BOARD_N {a["blocks"]["termination"]["parameters"]["differential_ohm"]}',
              f'VDD VDD 0 PWL(0n {v} 32n {v} 32.2n 0 44n 0 44.2n 1.5 52n 1.5 52.2n {v} 300n {v})',
              'XBUF VDD VSS BUF_REF BUF_BIAS TERM_VCM BUF_ENABLE '+cells['buffer']]
    for leg in ['P','N']:
        lines += [f'RB{leg} BOARD_{leg} BOND_{leg} {cfg["bond_resistance_ohm"]}',
                  f'LB{leg} BOND_{leg} PAD_{leg} {cfg["bond_inductance_h"]}']
    for name,nodes,key in [('RREF1','VDD BUF_REF','reference_top'),('RREF2','BUF_REF VSS','reference_bottom'),('RBIAS1','VDD BUF_BIAS','bias_top'),('RBIAS2','BUF_BIAS VSS','bias_bottom')]:
        lines.append(f'{name} {nodes} {cfg["bias_resistors_ohm"][key]}')
    lines += [f'CREF BUF_REF VSS {cfg["reference_capacitance_f"]}',f'CBIAS BUF_BIAS VSS {cfg["bias_capacitance_f"]}',
              f'CLOAD TERM_VCM VSS {cfg["termination_load_f"]}',
              'VTERM_ENABLE REQ_TERM_ENABLE 0 0','BCAS CASCODE 0 V=V(VDD)',
              f'VDATA DATA 0 PULSE(0 {v} 0 {edge} {edge} {period/2-edge} {period})',
              f'VPOSTDATA POSTDATA 0 PULSE(0 {v} {period/2} {edge} {edge} {period/2-edge} {period})',
              'VTX_RESET TX_RESET 0 0',f'VTX_QUALIFIED TX_QUALIFIED 0 {v}',
              'VBUF_REQUEST BUF_REQUEST VSS 0',
              f'BBUF_ENABLE BUF_ENABLE VSS V=V(BUF_REQUEST)*(V(VDD)>={low})*(V(VDD)<={high})',
              f'BCTL_OK CTL_OK VSS V=V(VDD)*(V(VDD)>={low})*(V(VDD)<={high})']
    for branch in ['MAIN','POST','TMDS','DETECT']:
        lines += [f'VEN_{branch} REQ_EN_{branch} 0 0',
                  f'BCTL_REQ_{branch} CTL_REQ_{branch} VSS V=V(VDD)*V(REQ_EN_{branch})',
                  f'BCTL_BOUNDARY_{branch} EN_{branch} VSS V=V(CTL_EN_{branch})/{v}']
        if branch=='DETECT':
            lines += [f'BDETECTBIAS DETECT_PBIAS 0 V=V(VDD)-{v-cfg["bias_v"][branch]}*V(EN_DETECT)',
                      'BDETECTEN DETECT_ENABLE 0 V=V(VDD)*V(EN_DETECT)']
        else:
            data='POSTDATA' if branch=='POST' else 'DATA'
            positive=f'({v}-V({data}))' if branch=='POST' else f'V({data})'
            negative=f'V({data})' if branch=='POST' else f'({v}-V({data}))'
            lines += [f'BBIAS_{branch} {branch}_BIAS 0 V={cfg["bias_v"][branch]}*V(EN_{branch})',
                      f'BP_{branch} {branch}_P 0 V={positive}*V(EN_{branch})',
                      f'BN_{branch} {branch}_N 0 V={negative}*V(EN_{branch})']
    lines += [f'BCTL_VALID_BOUNDARY TX_VALID VSS V=V(CTL_VALID)/{v}',
              'XCTL VDD VSS CTL_REQ_MAIN CTL_REQ_POST CTL_REQ_TMDS CTL_REQ_DETECT REQ_TERM_ENABLE TX_RESET TX_QUALIFIED CTL_OK CTL_CONFLICT CTL_VALID CTL_EN_MAIN CTL_EN_POST CTL_EN_TMDS CTL_EN_DETECT TERM_ENABLE '+cells['interlock']]
    if bias_resistance_ohm is not None:
        for branch in ('MAIN','POST'):
            prefix=f'BBIAS_{branch} {branch}_BIAS 0 '
            matches=[i for i,line in enumerate(lines) if line.startswith(prefix)]
            if len(matches)!=1:raise ValueError('Unexpected bias-source graph')
            i=matches[0];lines[i]=lines[i].replace(f'{branch}_BIAS 0',f'DRIVE_{branch}_BIAS 0',1)
            lines.append(f'RDRIVE_{branch} DRIVE_{branch}_BIAS {branch}_BIAS {bias_resistance_ohm}')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text('\n'.join(lines)+'\n')
    manifest=dict(scope=__doc__,bias_override=bias_override,bias_resistance_ohm=bias_resistance_ohm,
                  bias_driver_scope="Finite Thevenin reference boundary when resistance specified; source power not charged to VDD, no physical driver or precharge implied.",fixture_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),spec,arch,*models.values()]})
    output.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--pdk-model-dir',type=Path,required=True)
    a=p.parse_args();build(a.output.resolve(),a.pdk_model_dir.resolve())
