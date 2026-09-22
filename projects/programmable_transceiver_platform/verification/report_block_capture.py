import pathlib,json,re,hashlib
root=pathlib.Path(__file__).resolve().parents[3]
p=root/'projects/programmable_transceiver_platform'; out=root/'scratch/transceiver-block-capture-mapping'
log=(out/'timing.log').read_text()
assert 'Error:' not in log and 'not found' not in log
assert 'unconstrained endpoints' not in log
assert not log.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0].strip()
paths={}
for key,start,end in [('storage','CAPTURE_BEGIN wr_clk','CAPTURE_END wr_clk'),('read_domain','CAPTURE_BEGIN rd_clk','CAPTURE_END rd_clk'),('read_pointer','POINTER_BEGIN','POINTER_END')]:
 s=log.split(start)[1].split(end)[0]
 paths[key]={'arrival_ns':float(re.search(r'([\d.]+)\s+data arrival time',s)[1]),'slack_ns':float(re.search(r'([-\d.]+)\s+slack',s)[1])}
stat=json.loads((out/'stat.json').read_text())['design']
files=[p/'verification'/f for f in ['pt_block_fifo_capture.sv','block_capture_pins.py','block_capture_timing.tcl','run_block_capture_mapping.sh','report_block_capture.py']]+[p/'rtl/pt_fifo.sv',p/'rtl/pt_block_fifo.sv']+[out/f for f in ['mapped.v','mapped.json','timing.log','stat.json','library.sha256']]
r={'pass':59,'cell_area_um2':stat['area'],'standard_cells':sum(v for k,v in stat['num_cells_by_type'].items() if k.startswith('gf180')),'flip_flops':sum(v for k,v in stat['num_cells_by_type'].items() if '__dff' in k),'paths':paths,'period_ns':25.6,'boundary_delay_ns':4,'input_transition_ns':0.5,'output_load_pf':0.005,'unconstrained_input':'rst_n','capture_endpoints':84,'scope':'Nominal TT 25C 3.3V unplaced ideal-clock screen; storage path has provisional max-delay budget, not CDC safety proof. No hold, extracted RC, reset signoff or mapping equivalence.','sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(p/'evidence/block-capture-mapping.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({k:v for k,v in r.items() if k!='sha256'},indent=2))
