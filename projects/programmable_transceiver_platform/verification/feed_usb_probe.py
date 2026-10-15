"""USB quiet pads with differential reference loading and candidate feed controls."""
import hashlib
import json
import numpy as np
import baseline_envelope as b
from reference_input_probe import environment_port, differential_source_peak, reference_source_skew, probe_source_hashes
from design_definition import load_design


def feed_environment(design, resistance):
    nominal=design.architecture['blocks']['power']['parameters']['reduced_pdn_model']['network']['package_r']
    if resistance!=nominal:
        design=design.hypothetical(reason='USB feed-resistance mitigation experiment',
            changes={'blocks.power.parameters.reduced_pdn_model.network.package_r':resistance})
    environment,context=b.usb_supply_environment(design)
    context['probe_assumptions']=dict(
        source_differential_peak_v=differential_source_peak(environment),
        source_leg_skew_s=reference_source_skew(environment,0.),instantaneous_guard_v=.020,
        internal_switching='No assigned internal pulse spectrum; owner DC ceilings retained')
    return environment,context


def main():
    p=b.P;design=load_design();c=design.contract;opts=c['physical_services']['external_clock_input']['input_model']
    hashes=probe_source_hashes()
    hashes['verification/feed_usb_probe.py']=hashlib.sha256((p/'verification/feed_usb_probe.py').read_bytes()).hexdigest();rows=[]
    for resistance in (2.,1.):
        e,context=feed_environment(design,resistance)
        carrier=context['resolved_configuration']['reference_hz']
        ledger=b.partitioned_dc_ledger(e,dict(link_r_ohm=1e-5))
        sources=b.partitioned_host_sources(e);sources.setdefault(carrier,np.zeros(5,complex))
        for fixture,term,bonds in [('matched',(45.,45.),(2e-9,2e-9)),('asymmetric',(42.75,47.25),(1.6e-9,2.4e-9))]:
            legs=[[],[]];differential=[];local_diff=[];local_cm=[];board_cm=[];residual=0.
            dc=b.hs_pad_transfer(0.,termination_ohm=term,bond_l_h=bonds,capacitance_f=e['wired_pad_capacitance_f'])
            ground=ledger['die_return_v']/(1+e['network']['return_r_ohm']*sum(dc['ground_board'].real)/45.)
            dclegs=dc['ground_board'].real*ground
            dclocal=(dc['ground_die'].real-1)*ground
            for f,injection in sources.items():
                unloaded=environment_port(f,e,injection,source_diff=differential_source_peak(e) if f==carrier else 0.,**opts)
                unit=np.zeros(5);unit[3]=1.
                z=environment_port(f,e,unit,**opts)['network'][3]
                transfer=b.hs_pad_transfer(f,termination_ohm=term,bond_l_h=bonds,capacitance_f=e['wired_pad_capacitance_f'])
                y=sum(transfer['ground_board'])/45.
                g=unloaded['network'][3]/(1+z*y)
                # Independent recomputation with the feedback current applied.
                feedback=np.array(injection,complex);feedback[3]-=y*g
                closed=environment_port(f,e,feedback,source_diff=differential_source_peak(e) if f==carrier else 0.,**opts)
                residual=max(residual,float(abs(closed['network'][3]-g)))
                board=transfer['ground_board']*g
                local=(transfer['ground_die']-1)*g
                for target,value in ((local_diff,local[0]-local[1]),(local_cm,np.mean(local)),(board_cm,np.mean(board))):
                    target.append(dict(frequency_hz=f,clock_rail_voltage_peak_v=float(abs(value)),voltage_phase_rad=float(np.angle(value))))
                for i in (0,1):legs[i].append(dict(frequency_hz=f,clock_rail_voltage_peak_v=float(abs(board[i])),voltage_phase_rad=float(np.angle(board[i]))))
                d=board[0]-board[1];differential.append(dict(frequency_hz=f,clock_rail_voltage_peak_v=float(abs(d)),voltage_phase_rad=float(np.angle(d))))
            intervals=[b.rail_excursion(t,dc_v=float(v),samples_per_fastest_period=128) for t,v in zip(legs,dclegs)]
            peak=max(abs(v) for x in intervals for v in x['enclosed_interval_v'])
            assert residual<1e-10
            rows.append(dict(context,pad_fixture_assumptions=dict(termination_ohm=term,bond_l_h=bonds),local_feed_resistance_ohm=resistance,fixture=fixture,ledger=ledger,
                receiver_local_differential=b.rail_excursion(local_diff,dc_v=float(dclocal[0]-dclocal[1]),samples_per_fastest_period=128),
                receiver_local_common_mode=b.rail_excursion(local_cm,dc_v=float(np.mean(dclocal)),samples_per_fastest_period=128),
                board_common_mode=b.rail_excursion(board_cm,dc_v=float(np.mean(dclegs)),samples_per_fastest_period=128),
                released_pin_intervals=intervals,quiet_pin_enclosed_abs_peak_v=peak,
                instantaneous_20mv_guard_met=bool(peak<=.020),feedback_residual_v=residual,
                differential=b.rail_excursion(differential,dc_v=float(dclegs[0]-dclegs[1]),samples_per_fastest_period=128)))
            print(resistance,fixture,peak,flush=True)
    if hashes!={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in hashes}:
        raise RuntimeError('Sources changed during probe computation')
    b.write_evidence(p/'evidence/feed-usb-probe.json',dict(design_provenance=design.provenance(),cases=rows,sources_sha256=hashes,scope='Shared USB inventory and configured host rates with simplified released-pad fixtures. Shared-amplitude/skew 480 MHz differential reference loading/return and pad feedback solved together. No internal switching spectrum assigned; this is not a worst-case supply bound. Fixed source phases; no packet, squelch, chirp, cable or edge transients. The 20 mV instantaneous design guard is not an established compliance measurement. Clock sensitivity does not change these passive pin voltages.'))


if __name__=='__main__':main()
