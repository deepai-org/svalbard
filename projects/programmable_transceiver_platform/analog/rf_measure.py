"""Complex tone integration for nonuniform transient samples."""
import math

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

