"""Check phase integral wiring and forecast nonmutation before expensive acquisition."""
import copy,json
import numpy as np
from chip_model import P
from three_cap_pll import ThreeCapRFClock

def main():
    p=ThreeCapRFClock(filter_values=dict(r=25000,cf=12e-12,cs=30e-12,r3=20000,c3=3e-12),
        reference_hz=40e6,divider=60,free_hz=2.4e9,phase_cycles=.2)
    p.filter.state[:3]=[.15,.10,.05]
    assert p.frequency_hz==p.gains.free_hz+p.gains.kvco*.05
    # Reband transfer must retain all three physical capacitor charges.
    fresh=ThreeCapRFClock(filter_values=dict(r=25000,cf=12e-12,cs=30e-12,r3=20000,c3=3e-12),
        reference_hz=40e6,divider=60,free_hz=2.4e9,phase_cycles=.2)
    fresh.integral=p.integral
    np.testing.assert_allclose(fresh.filter.state[:3],p.filter.state[:3],rtol=1e-15)
    assert fresh.filter.energy==p.filter.energy
    for invalid in [(1e-12,2e-12),(float('nan'),0,0),(12e-12,0,0)]:
        saved=fresh.filter.state.copy()
        try:fresh.integral=invalid
        except ValueError:pass
        else:raise AssertionError('Invalid charge transfer accepted')
        assert np.array_equal(saved,fresh.filter.state)
    p.up=True;p.down=False
    state=p.filter.state.copy();phase=p.phase
    trial,forecast=p.predict(2e-9)
    assert np.array_equal(p.filter.state,state) and p.phase==phase and p.time==0
    independent=copy.copy(p.filter);independent.advance(2e-9,p.current)
    expected=phase+p.gains.free_hz*2e-9+p.gains.kvco*(independent.state[3]-state[3])
    assert abs(forecast-expected)<1e-12
    p.advance(50e-9)
    assert p.time==p.filter.time==50e-9 and p.fault is None
    saved=p.filter.state.copy()
    try:p.integral=fresh.integral
    except ValueError:pass
    else:raise AssertionError('Live charge overwrite accepted')
    assert np.array_equal(saved,p.filter.state)
    report=dict(charge_transfer='three nodes preserved; malformed, boundary and live writes rejected',status='passed_local_connection',phase_integral_error_cycles=abs(forecast-expected),
        final_nodes_v=p.filter.state[:3].tolist(),limitations=[
        '50ns connectivity test only, not acquisition, lock, noisy carrier quality or retune.',
        'Pump compliance uses pump node; legacy v property intentionally exposes VCO node.',
        'Filter compliance boundary raises rather than allowing extrapolated operation.'])
    (P/'evidence/three-cap-pll-screen.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
