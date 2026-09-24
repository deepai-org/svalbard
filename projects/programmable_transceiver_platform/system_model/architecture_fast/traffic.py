"""Timed-preparation adapter for the shared sustained-traffic harness."""
from sustained_lifecycle import run as run_shared, TrafficFault
from wired_return_lifecycle import DuplexChip


def run(mode,ppm,frames=128,chip_factory=DuplexChip,disturbance_sign=0,matched_reference=False,host_ppm=0,visibility_edges=0,source_phase_edges=0,service_pauses=None,waveform=None,prepare=None,startup_settle_s=0.):
    def startup(c,mode):
        if prepare is not None:prepare(c)
        startup=c.time;c.configure(mode,startup)
        if hasattr(c,'next_reference'):
            while c.state=='acquiring' and c.time<startup+10e-6:c.advance(c.next_reference)
        else:c.advance(startup+c.acquisition_s)
        assert c.state=='active'
        c.advance(max(c.time,startup+startup_settle_s))
        assert c.state=='active'
    return run_shared(mode,ppm,frames,chip_factory,disturbance_sign,matched_reference,
        host_ppm,visibility_edges,source_phase_edges,service_pauses,waveform,_startup=startup)
