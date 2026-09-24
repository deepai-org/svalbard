"""Complex tone integration for nonuniform transient samples."""
import bisect, math

def projection(points, index, start, stop, frequency):
    # Integrate nonuniform transient samples, inserting exact window endpoints.
    clipped = []
    for a, b in zip(points, points[1:]):
        if a[0] <= start < b[0]:
            f = (start-a[0])/(b[0]-a[0])
            clipped.append((start, a[index]+f*(b[index]-a[index])))
        if start < b[0] < stop:
            clipped.append((b[0], b[index]))
        if a[0] < stop <= b[0]:
            f = (stop-a[0])/(b[0]-a[0])
            clipped.append((stop, a[index]+f*(b[index]-a[index])))
    assert len(clipped) > 1000 and clipped[0][0] == start and clipped[-1][0] == stop
    def phasor(t):
        angle = -2*math.pi*frequency*t
        return complex(math.cos(angle), math.sin(angle))
    value = sum((b[0]-a[0])*(a[1]*phasor(a[0])+b[1]*phasor(b[0]))/2
                for a, b in zip(clipped, clipped[1:]))
    return 2*value/(stop-start)



def interpolate(rows, t, col):
    times = [r[0] for r in rows]
    k = bisect.bisect_left(times, t)
    a, b = (rows[k - 1], rows[k])
    return a[col] + (b[col] - a[col]) * (t - a[0]) / (b[0] - a[0])

def sampler_case(amplitude, samples, ph, window, currents):
    return dict(input_peak_v=amplitude, samples=samples, if_phasors=[[[z.real, z.imag] for z in row] for row in ph], hold_node_range_v=[min((r[c] for r in window for c in (5, 6, 7, 8))), max((r[c] for r in window for c in (5, 6, 7, 8)))], lna_sampler_current_a=currents[0], lo_current_a=currents[1])
