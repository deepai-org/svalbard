"""Pin/domain and limited measured-current planning screen, not PDN signoff."""
import hashlib
import json
from pathlib import Path
from check_contract import CONTRACT, require


def assess(contract, evidence):
    power=contract['power']
    pins={p['name']:p for p in contract['pins']}
    supplies={p['name'] for p in contract['pins'] if p['kind']=='supply'}
    returns={p['name'] for p in contract['pins'] if p['kind']=='ground'}
    domains=power['domains']; by_id={d['id']:d for d in domains}
    require(len(by_id)==len(domains),'duplicate power domain')
    owned_supply=[p for d in domains for p in d['supply_pins']]
    owned_return=[p for d in domains for p in d['return_pins']]
    require(len(set(owned_supply))==len(owned_supply) and set(owned_supply)==supplies,'supply ownership')
    require(len(set(owned_return))==len(owned_return) and set(owned_return)==returns,'return ownership')
    for d in domains:
        require(0<d['per_connection_budget_ma']<=power['supply_cell_dc_limit_ma'],'domain current budget')
        require(d['supply_pins'] and len(d['supply_pins'])==len(d['return_pins']),'domain supply/return count')
    segments=power['host_segments']
    require(len({s['id'] for s in segments})==len(segments),'duplicate host segment')
    for field, domain_field in [('supply','supply_pins'),('return','return_pins')]:
        assigned=[s[field] for s in segments]
        require(len(set(assigned))==len(assigned) and set(assigned)==set(by_id['HOST'][domain_field]),'host segment '+field)
    output_names=[p for s in segments for p in s['fast_outputs']]
    expected={f'D2H_D[{i}]' for i in range(10)}|{'D2H_CLK'}
    require(len(output_names)==len(set(output_names)) and set(output_names)==expected,'fast output ownership')
    input_names=[p for s in segments for p in s['inputs']]
    require(len(input_names)==len(set(input_names)) and set(input_names)=={f'H2D_D[{i}]' for i in range(10)}|{'H2D_CLK'},'input ownership')
    management=[p for s in segments for p in s['management']]
    require(len(management)==len(set(management)) and set(management)=={'HOST_CS_N','HOST_SCLK','HOST_MOSI','HOST_MISO','RESET_N'},'management ownership')
    require(all(p in pins and pins[p]['direction']=='out' for p in output_names),'output direction')
    require(all(p in pins and pins[p]['direction']=='in' for p in input_names),'input direction')
    require(power['screen_output_current_multiplier']>=1,'invalid screening multiplier')
    require(power['screen_other_current_allowance_ma_per_segment']>=0,'invalid current allowance')
    rows=[]
    selected=[r for r in evidence['results'] if r['pattern']=='alternating']
    require({r['mos_corner'] for r in selected}=={'typical','ss'} and len(selected)==2,'missing/duplicate alternating evidence')
    for r in selected:
        require(r['sampled_bits']==20 and r['external_lumped_capacitance_pf_per_output']==5,'unexpected evidence scope')
        per_output=r['two_pad_dvdd_average_a']*1000/2
        require(per_output>0,'invalid measured current')
        for segment in segments:
            estimate=per_output*len(segment['fast_outputs'])
            allowance=estimate*power['screen_output_current_multiplier']+power['screen_other_current_allowance_ma_per_segment']
            rows.append({'case':r['case'],'segment':segment['id'],'fast_outputs':len(segment['fast_outputs']),
                         'scaled_average_ma':estimate,'with_provisional_allowances_ma':allowance,
                         'planning_budget_ma':by_id['HOST']['per_connection_budget_ma'],
                         'within_planning_budget':allowance<=by_id['HOST']['per_connection_budget_ma']})
    return {'scope':'two-pad-current extrapolation only; not bank simulation or power qualification',
            'all_host_estimates_within_candidate_budget':all(r['within_planning_budget'] for r in rows),
            'rows':rows,'unqualified_domains':[d['id'] for d in domains],
            'limitations':['25% multiplier and 2 mA allowance are design assumptions, not measured bounds.',
            'No FF/hot/high-VDD bank current, peak/SSO, clamp, ground distribution or package data.',
            'Digital core now has one supply/return pair and a 48 mA ceiling; no core power estimate proves it fits.',
            'Two segments require actual rail separation and dedicated returns; pad counts alone do not establish it.']}


if __name__=='__main__':
    c=json.loads(CONTRACT.read_text());p=CONTRACT.parents[1]/c['power']['current_evidence']
    result=assess(c,json.loads(p.read_text()))
    result['contract_sha256']=hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    result['evidence_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    print(json.dumps(result,indent=2))
    require(result['all_host_estimates_within_candidate_budget'],'host-current planning ceiling exceeded')
