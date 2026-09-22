"""Current common-model evidence audit; never equates test passes with closure."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]
F=P/'system_model/architecture_fast';sys.path.insert(0,str(F))
from chip import TransceiverChip

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
    loaded=hasattr(c,'loaded_tx')
    out=dict(status='completed',evidence=rows,observed_common_configuration=dict(
        receiver_filter_order=len(c.tx.rx_bank['poles']),receiver_cutoff_hz=c.tx.rx_bank['cutoff_hz'],
        shared_reference=c.adc_reference is c.dac_reference,
        finite_loaded_tx_network_instantiated=loaded,
        adc_latency_s=c.adc_latency),
        mathematical_closure=False,transistor_schematic_complete=False,layout_gate_open=False,
        next_priority='Integrate phase-aware finite TX output network into common chip, detector, loopback and independent pad observation; requalify transport and quality.',
        remaining=['Finite output loading/current and supply interaction are not represented by memoryless output observation.',
            'Warm coarse clocks are a tested subclass, not the default common composition.',
            'Pin-level management/RTL agreement, general service and configuration envelopes remain open.',
            'Reference current/bandwidth limits and all physical block parameters need circuit evidence.'],
        implementation_sources={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in [Path(__file__),F/'chip.py',F/'output_loopback.py',
                      P/'system_model/connected/loaded_tx_chip.py']})
    (P/'evidence/fast-model-audit.json').write_text(json.dumps(out,indent=2)+'\n')
    assert all(row['current'] for row in rows),'Current baseline evidence is stale or failed'
    print(json.dumps(out['observed_common_configuration'],indent=2))
    print(out['next_priority'])
if __name__=='__main__':main()
