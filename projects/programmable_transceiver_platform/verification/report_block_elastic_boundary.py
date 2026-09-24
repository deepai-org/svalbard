from timing_log import reported_paths
import pathlib,json,re,hashlib
root=pathlib.Path(__file__).resolve().parents[3];p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-block-elastic-boundary'
prior=json.loads((p/'evidence/block-elastic-physical.json').read_text());name='scratch/transceiver-block-elastic-physical/digital.odb'
assert hashlib.sha256((root/name).read_bytes()).hexdigest()==prior['sha256'][name]
cases={}
for corner in ('tt_025C_3v30','ff_n40C_3v60','ss_125C_3v00'):
 text=(out/(corner+'.log')).read_text();assert 'Error:' not in text and 'not found' not in text
 groups={}
 for domain in ('wr_clk','rd_clk'):
  for kind in ('max','min'):
   section=text.split('DOMAIN_BEGIN '+domain+' '+kind+'\n')[1].split('DOMAIN_END')[0]
   for group in (domain,'asynchronous'):
    paths=reported_paths(section,group)
    if paths:groups[domain+':'+kind+':'+group]=min(paths,key=lambda x:x['slack_ns'])
 assert not text.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0].strip()
 assert 'unconstrained endpoints' not in text
 cases[corner]=groups
assert cases['ss_125C_3v00']['wr_clk:min:wr_clk']['slack_ns']<0
files=[p/'verification'/f for f in ('block_elastic_boundary.tcl','block_elastic_boundary.py','run_block_elastic_boundary.sh','report_block_elastic_boundary.py')]+list(out.glob('*.log'))
files.append(p / 'verification/timing_log.py')
r={'pass':68,'status':'boundary hold fails under provisional zero-minimum input arrival','corners':cases,'scope':'Same-domain setup/hold/recovery/removal with provisional IO budgets and 0.5ns hold uncertainty. CTS/placement RC only; cross-domain paths not qualified.','sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(p/'evidence/block-elastic-boundary.json').write_text(json.dumps(r,indent=2)+'\n')
print(r['status'])
