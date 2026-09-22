"""Cut corresponding registers to prove mapped combinational next-state equivalence."""
import copy
import hashlib
import json
from pathlib import Path
import sys

gold_path,gate_path,out=map(Path,sys.argv[1:4]);out.mkdir(parents=True,exist_ok=True)
gold=json.loads(gold_path.read_text())['modules']['pt_digital']
gate=json.loads(gate_path.read_text())['modules']['pt_digital']
def registers(m):return {k:v for k,v in m['cells'].items() if '__dff' in v['type']}
gf,tf=registers(gold),registers(gate)
assert gf and gf.keys()==tf.keys(),'register correspondence changed'
assert gold['ports'].keys()==gate['ports'].keys(),'top interface changed'
for p in gold['ports']:
    assert gold['ports'][p]['direction']==gate['ports'][p]['direction']
    assert len(gold['ports'][p]['bits'])==len(gate['ports'][p]['bits'])
for n in gf:
    assert gf[n]['type']==tf[n]['type'] and gf[n]['parameters']==tf[n]['parameters'],n
    assert gf[n]['port_directions']==tf[n]['port_directions'],n
    assert set(gf[n]['connections'])==set(tf[n]['connections']),n
    assert gf[n]['port_directions'].get('Q')=='output'
    assert [p for p,d in gf[n]['port_directions'].items() if d=='output']==['Q']
observations=0
for label,mod in [('gold',gold),('gate',gate)]:
    m=copy.deepcopy(mod);m['attributes']={}
    obs=0;qbits=[]
    for i,name in enumerate(sorted(gf)):
        cell=m['cells'].pop(name);q=cell['connections']['Q'];assert len(q)==1
        qbits.extend(q)
        m['ports'][f'proof_state_{i}']={'direction':'input','bits':q}
        for pin in sorted(cell['connections']):
            if pin=='Q':continue
            assert cell['port_directions'][pin]=='input'
            m['ports'][f'proof_observe_{i}_{pin}']={'direction':'output','bits':cell['connections'][pin]}
            obs+=len(cell['connections'][pin])
    assert len(set(qbits))==len(qbits),'shared register outputs require explicit correspondence'
    m['cells']={k:v for k,v in m['cells'].items() if v['type']!='$scopeinfo'}
    for pname,pvalue in m['ports'].items():
        if pname in m['netnames']:
            assert pvalue['bits']==m['netnames'][pname]['bits'],('port/net mismatch',pname)
    (out/f'{label}-cut.json').write_text(json.dumps({'modules':{label:m}}))
    if label=='gate':
        negative=copy.deepcopy(m)
        bit=negative['ports']['status']['bits'][0]
        allbits=[b for v in negative['netnames'].values() for b in v['bits'] if isinstance(b,int)]
        changed=max(allbits)+1
        negative['cells']['proof_intentional_error']={'hide_name':0,'type':'$not',
          'parameters':{'A_SIGNED':'0','A_WIDTH':'1','Y_WIDTH':'1'},'attributes':{},
          'port_directions':{'A':'input','Y':'output'},'connections':{'A':[bit],'Y':[changed]}}
        negative['ports']['status']['bits'][0]=changed
        negative['netnames']['status']['bits'][0]=changed
        for pname,pvalue in negative['ports'].items():
            if pname in negative['netnames']:
                assert pvalue['bits']==negative['netnames'][pname]['bits'],('port/net mismatch',pname)
        (out/'gate-negative.json').write_text(json.dumps({'modules':{'gate':negative}}))
    observations=obs
report={'scope':'Mapped-state correspondence and combinational next-state/output equivalence; not RTL-to-gates or physical verification',
        'gold_sha256':hashlib.sha256(gold_path.read_bytes()).hexdigest(),
        'gate_sha256':hashlib.sha256(gate_path.read_bytes()).hexdigest(),
        'matched_registers':len(gf),'register_input_bits_observed':observations,
        'top_output_bits':sum(len(p['bits']) for p in gold['ports'].values() if p['direction']=='output'),
        'method':'Corresponding Q values are shared arbitrary inputs; compare every D/CLK/reset/set input and top output. Cell types and port directions must match.',
        'proof_status':'pending SAT'}
(out/'equivalence-inputs.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'Cut {len(gf)} matched registers; comparing {observations} register input bits plus top outputs')
