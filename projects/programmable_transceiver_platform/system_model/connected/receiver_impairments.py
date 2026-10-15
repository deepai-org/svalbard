"""Standalone sampled frontend sensitivity; not RF compression or chip integration."""
import math,random

class Frontend:
    def __init__(self,gain_error=0,phase_error=0,saturation=None,noise_rms=0,seed=783):
        if not all(math.isfinite(v) for v in (gain_error,phase_error,noise_rms)) or abs(gain_error)>=1 or noise_rms<0:
            raise ValueError('Invalid frontend parameters')
        if saturation is not None and (not math.isfinite(saturation) or saturation<=0):raise ValueError('Invalid saturation')
        self.g=gain_error;self.p=phase_error;self.sat=saturation;self.noise=noise_rms
        self.rng=random.Random(seed);self.count=0;self.error_energy=0.;self.signal_energy=0.
    def sample(self,z):
        if not math.isfinite(z.real) or not math.isfinite(z.imag):raise ValueError('Nonfinite frontend input')
        # Q basis rotated from orthogonality; gains vary symmetrically around1.
        w=complex((1+self.g)*z.real+(1-self.g)*z.imag*math.sin(self.p),
                  (1-self.g)*z.imag*math.cos(self.p))
        if self.sat is not None:w/=math.sqrt(1+abs(w)**2/self.sat**2)
        if self.noise:w+=complex(self.rng.gauss(0,self.noise),self.rng.gauss(0,self.noise))
        self.count+=1;self.error_energy+=abs(w-z)**2;self.signal_energy+=abs(z)**2
        return w


def controls():
    ideal=Frontend()
    for z in (0j,1+2j,-.25+.13j):assert ideal.sample(z)==z
    f=Frontend(gain_error=.1);assert abs(f.sample(1j)-.9j)<1e-15
    f=Frontend(phase_error=.2);assert abs(f.sample(1j)-complex(math.sin(.2),math.cos(.2)))<1e-15
    f=Frontend(saturation=.5)
    assert abs(f.sample(100))<.5 and f.sample(.3j)==-f.sample(-.3j)
    a=Frontend(noise_rms=.01);b=Frontend(noise_rms=.01)
    assert [a.sample(0j) for _ in range(100)]==[b.sample(0j) for _ in range(100)]
    noise=Frontend(noise_rms=.01)
    values=[noise.sample(0j) for _ in range(30000)]
    power=sum(abs(v)**2 for v in values)/len(values)
    assert abs(power/.0002-1)<.03


if __name__=="__main__":
    controls()
    print("Standalone numerical controls passed; no chip lifecycle exercised.")
