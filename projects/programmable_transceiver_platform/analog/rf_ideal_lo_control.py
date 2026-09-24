#!/usr/bin/env python3
"""Ideal LO controls on the fixed LNA/mixer/filter/sampling chain."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
from rf_autonomous_chain_screen import sampled_chain, __file__ as chain_source
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--limited-swing',action='store_true');parser.add_argument('--if-cap-pf',type=float,default=1);parser.add_argument('--prebias',action='store_true');args=parser.parse_args()
O=Path('/work');base=(Path('/clock')/'v3.3.spice').read_text()
f=json.loads((Path('/clock')/'result.json').read_text())['cases'][0]['frequency_hz']
low,high=(.125,3.099) if args.limited_swing else (0,3.3)
period=1/f
# Keep oscillator/buffers, but disconnect their outputs from mixer gates.
base=base.replace('XMIX DRAIN LO LOB', 'XMIX DRAIN TESTLO TESTLOB')
base=base.replace('.control',f'VTESTLO TESTLO 0 PULSE({low} {high} 0 20p 20p {period/2-20e-12} {period})\nVTESTLOB TESTLOB 0 PULSE({high} {low} 0 20p 20p {period/2-20e-12} {period})\n.control')
assert args.if_cap_pf>0
base=base.replace('CIP IP 0 1p',f'CIP IP 0 {args.if_cap_pf:g}p').replace('CIN INN 0 1p',f'CIN INN 0 {args.if_cap_pf:g}p')
if args.prebias:base=base.replace('.control','.ic v(GATE)=1.5\n.control')
rows,y,x,c=sampled_chain(base,f,O)
r=dict(status='ideal_lo_control_not_autonomous_receiver',prebiased_gate=args.prebias,if_cap_per_leg_pf=args.if_cap_pf,lo_low_v=low,lo_high_v=high,lo_edge_s=20e-12,cases=rows,rf_hz=f+10e6,nominal_if_hz=10e6,baseline_subtracted_samples_v=y.tolist(),held_tone_gain=float(np.hypot(c[1],c[2])/.001),fit_residual_rms_v=float(np.sqrt(np.mean((y-x@c)**2))),runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),limitations=['Ideal complementary LO at the prior measured frequency; oscillator and buffers remain but lose mixer gate loading. Rail currents not directly comparable.', 'One branch, no quadrature or ADC; ideal 40MS/s sampling clock and biases.', 'Seeded oscillator, no PLL, intrinsic phase noise, mismatch, PEX, package or pad model.', 'Eight held samples and paired zero subtraction are a diagnostic, not EVM/SNR/ENOB.', 'RF frequency selected using preceding clock measurement; not demonstrated channel tuning or acquisition.', 'Added filter loading may pull oscillator and alter frequency; fixed 10MHz fit is diagnostic.'])
r['shared_runner_sha256']=hashlib.sha256(Path(chain_source).read_bytes()).hexdigest()
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n')
