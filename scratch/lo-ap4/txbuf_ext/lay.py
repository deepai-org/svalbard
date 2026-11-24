import sys,json
T='/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'
sys.path.insert(0,T)
import timing_flow as tf
r=tf.build_layout('lo_txbuf', publish='never', max_row_width=float(sys.argv[1]) if len(sys.argv)>1 else 160.0)
print(json.dumps(r, default=str)[:1500])
