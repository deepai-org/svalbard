import sys; from pathlib import Path
sys.path.insert(0,'/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx')
import wrx_flow as f
H=Path(__file__).resolve().parent
for top in sys.argv[1:]:
    sub=f.parse_spice(H/'t.spice', top); w=H/top
    lay=f.generate_layout(sub,w,over_dev=True,trunks_over=True)
    ref=f.lvs_reference(H/'t.spice',top,lay.get('antenna_diodes'),w/'ref.spice')
    lv=f.lvs(w,f'{top}.lvs.spice',top,ref,top)
    print(top,'drc',lay['drc_count'],'lvs',lv['unique_match'],lv['final_result'],flush=True)
