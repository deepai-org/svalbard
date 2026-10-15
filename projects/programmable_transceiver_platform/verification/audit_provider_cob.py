"""Read the pinned public Run 1 COB board; no layout editing or RF qualification.

Usage: python3 audit_provider_cob.py /path/to/chip-on-board-wire-bonded-pcbs
"""
import hashlib,json,re,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/architecture_fast'))
from design_definition import load_design
COMMIT='4f05ed1ea1994d8101a265d5d4f995bcea86d5a1'
BOARD='run-1/1x1-cob/1x1-mezzanine.kicad_pcb'


def children(node,key):
    return [x for x in node if isinstance(x,list) and x and x[0]==key]


def parse(text):
    root=[];current=root;stack=[]
    for token in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text):
        if token=='(':
            new=[];current.append(new);stack.append(current);current=new
        elif token==')':current=stack.pop()
        else:current.append(json.loads(token) if token.startswith('"') else token)
    if stack or len(root)!=1:raise ValueError('Malformed PCB expression')
    return root[0]


def audit(repository, *, design=None):
    design=load_design() if design is None else design
    commit=subprocess.check_output(['git','-C',str(repository),'rev-parse','HEAD'],text=True).strip()
    if commit!=COMMIT:raise ValueError('Different provider revision; review before updating pinned evidence')
    path=repository/BOARD;raw=path.read_bytes()
    committed=subprocess.check_output(['git','-C',str(repository),'show',f'{COMMIT}:{BOARD}'])
    if raw!=committed:raise ValueError('Provider PCB worktree differs from pinned source')
    board=parse(raw.decode());footprints={};components=[]
    for fp in children(board,'footprint'):
        props={x[1]:x[2] for x in children(fp,'property')};ref=props.get('Reference')
        if not ref or ref.startswith('G'):continue
        pads={x[1]:children(x,'net')[0][1] for x in children(fp,'pad') if x[1] and children(x,'net')}
        footprints[ref]=pads
        components.append(dict(reference=ref,value=props.get('Value'),nets=sorted(set(pads.values()))))
    bond={int(k):v for k,v in footprints['U102'].items() if k.isdigit() and int(k)<=74}
    connector={int(k):v for k,v in footprints['U101'].items() if k.isdigit()}
    assert set(bond)==set(range(1,75)) and set(connector)==set(range(1,71))
    c=design.contract;a=c['assembly_policy']
    sides=a['provider_site_inventory']['ordered_sites_by_side']
    # Candidate orientation inference: first south site is board pad_0; west
    # list reverses to preserve the documented complete fixed-supply sequence.
    sites=sides['south']+sides['east']+sides['north']+list(reversed(sides['west']))
    ordinal={site:i+1 for i,site in enumerate(sites)}
    supplies=[]
    for site,n in ordinal.items():
        if site.startswith(('dvss_pads','vss_pads')):
            assert bond[n]=='GND',(site,n,bond[n])
        elif site.startswith(('dvdd_pads','vdd_pads')):
            assert not bond[n].startswith('/') and bond[n]!='GND'
            supplies.append(dict(site=site,bond_pad=n,board_net=bond[n],connector_contacts=[k for k,v in connector.items() if v==bond[n]]))
        else:assert bond[n].startswith('/pad_'),(site,n,bond[n])
    signals=[]
    for signal,site in a['candidate_signal_sites'].items():
        number=ordinal[site];net=bond[number];contacts=[k for k,v in connector.items() if v==net]
        assert len(contacts)==1,(signal,net,contacts)
        loads=[x['reference'] for x in components if x['reference'] not in ('U101','U102') and net in x['nets']]
        signals.append(dict(signal=signal,site=site,bond_pad=number,board_net=net,connector_contact=contacts[0],other_component_references=loads))
    return dict(status='public_run1_connectivity_evidence_not_current_assembly_signoff',qualified=False,
        provider_commit=COMMIT,board_path=BOARD,board_sha256=hashlib.sha256(raw).hexdigest(),
        source_url=f'https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs/blob/{COMMIT}/{BOARD}',
        die_bond_sites=74,connector_numbered_contacts=70,
        connector_ground_contacts=[k for k,v in connector.items() if v=='GND'],
        common_ground_net='GND',distinct_supply_nets=sorted({x['board_net'] for x in supplies}),
        supply_mapping=supplies,candidate_signal_mapping=signals,components=components,
        design_provenance=design.provenance(),
        configuration_scope='assembly_connectivity_audit_not_active_signal_configuration',
        limitations=['Run 1 only; provider explicitly says later-run pinouts and footprints may change.',
            'South-origin/west-reversal die-to-board permutation inferred from fixed-power sequence; verify against actual GDS and wirebond drawing before freezing signal names.',
            'Signal netnames and component connectivity are read from PCB source; routed impedance, copper integrity, loading and connector bandwidth are not qualified.',
            'Eight distinct board supply nets do not prove isolated on-die rails. Default foundry-pad chip_top ties supplies; segmentation remains a separate design question.',
            'Capacitor footprints labeled 1 uF do not prove actual populated values or high-frequency decoupling.',
            'Extra U102 ground shapes and U101 MP pads are not additional numbered signal contacts; physical grounding geometry remains to be modeled.'])


if __name__=='__main__':
    result=audit(Path(sys.argv[1]))
    (P/'evidence/provider-cob-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f"Verified source inventory: {result['die_bond_sites']} bond sites, {result['connector_numbered_contacts']} numbered contacts, {len(result['distinct_supply_nets'])} supply nets; candidate signals {len(result['candidate_signal_mapping'])}.")
