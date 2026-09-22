"""Local driver rail → reference connection over declared coupling intervals.

The driver solve is independent of reference current in this candidate. Linear
interpolation uses solved interval endpoints; converter impulses split intervals.
"""
import copy,math

def advance(driver,reference,end,command,step_s=1e-9):
    if not math.isfinite(end) or not math.isfinite(step_s) or step_s<=0 or end<driver.time or reference.time!=driver.time:
        raise ValueError('Aligned driver/reference clocks required')
    d=copy.copy(driver);d.network=copy.deepcopy(driver.network)
    d.detector=copy.copy(driver.detector) if driver.detector is not None else None
    r=copy.copy(reference)
    while d.time<end:
        start=d.time;stop=min(end,start+step_s);initial=d.rail_v
        d.advance(stop,command,max_step=step_s)
        slope=(d.rail_v-initial)/(stop-start)
        r.set_driver_rail(start,initial,slope);r.advance(stop)
        r.set_driver_rail(stop,d.rail_v,0.)
    driver.network.__dict__.update(d.network.__dict__)
    if driver.detector is not None:driver.detector.__dict__.update(d.detector.__dict__)
    driver.time=d.time;driver.rail_v=d.rail_v;reference.__dict__.update(r.__dict__)
