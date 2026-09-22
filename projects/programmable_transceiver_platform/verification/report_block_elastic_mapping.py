import pathlib,json,re,hashlib
root=pathlib.Path(__file__).resolve().parents[3];p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-block-elastic-mapping'
stat=json.loads((out/'stat.json').read_text())['design'];cone=json.loads((out/'cone.json').read_text());log=(out/'timing.log').read_text()
assert cone=={'capture_bits':168,'capacity_registers':1,'rd_ready_to_capture_combinational_path':False}
assert 'Error:' not in log and 'Warning:' not in log
paths={}
for kind in ('max','min'):
 section=log.split('CAPACITY_BEGIN '+kind+'\n')[1].split('CAPACITY_END')[0]
 endpoints=set(re.findall(r'Endpoint: (\S+)',section));slacks=[float(x) for x in re.findall(r'([-\d.]+)\s+slack',section)]
 assert len(endpoints)==len(slacks)==168
 paths[kind]=min(slacks)
assert not log.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0].strip()
files=[p/'rtl'/f for f in ('pt_fifo.sv','pt_block_fifo.sv','pt_block_elastic.sv')]+[p/'verification'/f for f in ('block_elastic_pins.py','block_elastic_timing.tcl','run_block_elastic_mapping.sh','report_block_elastic_mapping.py')]+[out/f for f in ('mapped.v','mapped.json','stat.json','timing.log','library.sha256','cone.json')]
r={'pass':66,'area_um2':stat['area'],'flip_flops':sum(n for k,n in stat['num_cells_by_type'].items() if '__dff' in k),'capacity_path_slack_ns':paths,'cone':cone,'scope':'Nominal TT25C3.3V ideal clocks no wire RC; capacity-register-to-receiving-storage paths only. No whole-interface timing, physical CDC, mapped functional equivalence or tapeout signoff.','sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(p/'evidence/block-elastic-mapping.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='sha256'},indent=2))
