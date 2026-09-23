"""Current common-model evidence audit; never equates test passes with closure."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]
F=P/'system_model/architecture_fast';sys.path.insert(0,str(F))
from chip import TransceiverChip
from warm_chip import WarmTransceiverChip
from fast_exclusive_engine import PoweredExclusiveChip,IntegratedTransceiverChip

def main():
    c=TransceiverChip()
    reports=['fast-common-acceptance.json','fast-blocker-quality.json',
             'fast-profile-load-quality.json','fast-signed-coupling-quality.json']
    rows=[]
    for name in reports:
        path=P/'evidence'/name;r=json.loads(path.read_text())
        mismatches=[n for n,h in r['source_sha256'].items()
                    if not (P/n).exists() or hashlib.sha256((P/n).read_bytes()).hexdigest()!=h]
        bad_results=[]
        for check in r.get('checks',[]):
            result=P/'evidence'/check['evidence']
            if not result.exists() or hashlib.sha256(result.read_bytes()).hexdigest()!=check['result_sha256']:
                bad_results.append(check['evidence'])
        rows.append(dict(evidence=name,status=r['status'],source_mismatches=mismatches,
            result_mismatches=bad_results,current=r['status']=='passed' and not mismatches and not bad_results,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    loaded=hasattr(c,'output_network')
    compositions=[]
    for name,model in (('common',c),('warm',WarmTransceiverChip()),('powered_loaded',PoweredExclusiveChip()),('integrated',IntegratedTransceiverChip())):
        compositions.append(dict(name=name,implementation=type(model).__name__,
            finite_output_network=hasattr(model,'output_network'),
            coarse_tuning=hasattr(model,'coarse'),
            engine_ownership=hasattr(model,'active_engine'),
            oscillator_shutdown=hasattr(model.rf_pll,'set_power'),
            reference_model=type(model.adc_reference).__name__,
            reference_current_limit_exposed=any(hasattr(model.adc_reference,n) for n in ('current_limit','source_current_limit','max_current'))))
    contract=json.loads((P/'spec/contract.json').read_text())
    out=dict(status='completed',evidence=rows,composition_inventory=compositions,
        budget_inventory=dict(area_allocation_um2=contract['area_um2'],power_status=contract['power']['status'],
            implementation_area_sum_available=False,whole_chip_current_sum_available=False),observed_common_configuration=dict(
        receiver_filter_order=len(c.tx.rx_bank['poles']),receiver_cutoff_hz=c.tx.rx_bank['cutoff_hz'],
        shared_reference=c.adc_reference is c.dac_reference,
        finite_loaded_tx_network_instantiated=loaded,
        adc_latency_s=c.adc_latency),
        mathematical_closure=False,transistor_schematic_complete=False,layout_gate_open=False,
        next_priority='Complete reference-loss/recovery on the integrated composition, then replace unlimited reference/output drive assumptions with finite-current shared supply behavior and reconcile whole-chip budgets.',
        remaining=['IntegratedTransceiverChip combines coarse/warm tuning, loaded output, ownership and shutdown; initial same-instance RF/wired retune lifecycle passes, but full recovery and quality coverage remain open.',
            'Reference.advance replenishes charge by ideal RC relaxation to a fixed source; no explicit driver current limit in these compositions.',
            'Power-domain ceilings and area allocations are targets, not sums from implemented blocks and active modes.',
            'Pin-level management/RTL agreement and declared host/service envelopes remain open.',
            'Architecture flags establish implementation presence only, not verified operation or physical performance.'],
        implementation_sources={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in [Path(__file__),F/'chip.py',F/'output_loopback.py',
                      F/'warm_chip.py',F/'coarse_chip.py',
                      P/'verification/fast_exclusive_engine.py',P/'verification/fast_loaded_output.py',
                      P/'system_model/connected/causal_reference_lifecycle.py',P/'spec/contract.json']})
    (P/'evidence/fast-model-audit.json').write_text(json.dumps(out,indent=2)+'\n')
    assert all(row['current'] for row in rows),'Current baseline evidence is stale or failed'
    print(json.dumps(out['observed_common_configuration'],indent=2))
    print(out['next_priority'])
if __name__=='__main__':main()
