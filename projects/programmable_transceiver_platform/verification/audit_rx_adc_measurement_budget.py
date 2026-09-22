#!/usr/bin/env python3
"""Audit inherited stimulus suitability; no prediction of loaded RF performance."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
E=P/'evidence/bb-connected-bypass-conversion.json';S=P/'evidence/rx-adc-schedule.json'
e=json.loads(E.read_text());s=json.loads(S.read_text());assert e['completed'] and s['seven_source_shift_verified']
f=next(f for c in e['cases'] if c['name']=='tone' for f in c['fits'] if f['window_ns']==[240,400] and f['lo_harmonic_fit_order']==8)
holds=[x['hold_start_ns'] for x in s['frames']];assert holds[2]-holds[1]==holds[1]-holds[0]
fs=1e9/(holds[1]-holds[0]);fif=f['if_frequency_hz'];alias=(fif+fs/2)%fs-fs/2
# Nominal differential SAR range +/- (VH-VL), excluding observed rail error.
step=2*(2.15-1.15)/256
out=dict(prior_conversion_evidence_sha256=sha(E),schedule_evidence_sha256=sha(S),sample_rate_per_channel_hz=fs,prior_unloaded_if_hz=fif,prior_if_alias_hz=alias,nominal_differential_step_v=step,prior_peak_steps={c:f[f'filter_{c}_peak_v']/step for c in ('i','q')},status='loading_fixture_not_signal_quality_qualification',next_measurement_requirements=['Retain current loaded/isolated comparison for startup and back-loading evidence.','Use a tone comfortably within +/-10MHz for this20MS/s profile; determine IF from actual LO, not nominal control.','Establish programmable analog gain and input headroom so a useful tone exercises multiple codes without compression.','Use sufficient samples and matched no-tone histories before dynamic distortion/noise interpretation; three frames cannot qualify ENOB.'],limitations=['Prior unloaded open-loop receiver fit; current loaded amplitude and LO may differ.','Nominal step is an ideal symmetric8bit range calculation, not measured DNL or ENOB.','Do not raise RF amplitude and silently assume linearity to compensate for missing gain.'])
(P/'evidence/rx-adc-measurement-budget.json').write_text(json.dumps(out,indent=2)+'\n');print(fs,fif,alias,out['prior_peak_steps'])
