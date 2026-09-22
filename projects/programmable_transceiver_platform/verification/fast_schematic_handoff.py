"""Audit source/evidence availability at the mathematical-to-schematic boundary."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
ROOT=P.parents[1]
def record(name):
    f=ROOT/name
    row=dict(path=name,exists=f.is_file())
    if f.is_file():row['sha256']=hashlib.sha256(f.read_bytes()).hexdigest()
    return row

def main():
    spec=P/'spec/schematic-implementation.json'
    inventory=json.loads(spec.read_text())
    rows=[]
    for block in inventory['blocks']:
        sources=[record(n) for n in block.get('source_paths',[])]
        evidence=[record(n) for n in block.get('evidence_paths',[])]
        rows.append(dict(id=block['id'],inventory_status=block['status'],sources=sources,evidence=evidence,
            inventory_gap=block.get('gap',''),completion_proven=False,
            reason='Artifact presence and inventory labels do not establish circuit performance.'))
    result=dict(status='audit_completed',schematic_complete=False,layout_gate_open=False,
        inventory_sha256=hashlib.sha256(spec.read_bytes()).hexdigest(),blocks=rows,
        priority=[
          dict(block='rf_synthesizer/rf_receive',gap='Loaded LO threshold continuity and reference spur; ideal fast mixers do not expose this failure.',next_evidence='Autonomous loaded mixer-clock crossings and RX spur/noise against explicit acceptance limits.'),
          dict(block='bias_reference_startup/radio_adc',gap='Reference regulation and converter signal accuracy under actual load are not established.',next_evidence='Connected converter/reference startup, settling and signal-quality measurements.'),
          dict(block='whole_chip_analog',gap='No integrated whole-chip transistor schematic listed.',next_evidence='One explicit hierarchy connecting RF, wired clocks/paths, converters, bias, pads and controls.')],
        limitations=['Inventory may contain historical runs; no running/terminal inference is made from text.',
                     'Hashes capture current files but do not establish every historical result matches current source.',
                     'No fabrication assurance or schematic/layout completion inferred from mathematical tests.'])
    out=P/'evidence/fast-schematic-handoff.json';out.write_text(json.dumps(result,indent=2)+'\n')
    missing=[x['path'] for b in rows for x in b['sources']+b['evidence'] if not x['exists']]
    print(json.dumps(dict(blocks=len(rows),missing_artifacts=missing,schematic_complete=False)))
if __name__=='__main__':main()
