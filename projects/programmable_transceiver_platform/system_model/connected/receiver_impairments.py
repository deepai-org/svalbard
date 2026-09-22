"""Sampled baseband frontend impairments; parameters are sensitivity assumptions."""
import json,math,random
from chip_model import P
from causal_reference_lifecycle import ReferenceChip
from sustained_lifecycle import run

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

class ImpairedChip(ReferenceChip):
    def __init__(self,frontend=None,**kwargs):
        super().__init__(**kwargs);self.frontend=Frontend(**(frontend or {}))
    def convert_adc(self,value):return super().convert_adc(self.frontend.sample(value))
    def reference_metrics(self):
        result=super().reference_metrics();f=self.frontend
        result['frontend']=dict(samples=f.count,relative_rms_error=math.sqrt(f.error_energy/f.signal_energy) if f.signal_energy else None,
            gain_error=f.g,phase_error_rad=f.p,saturation=f.sat,noise_rms_per_component=f.noise)
        return result


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


def main():
    controls();rows=[]
    for mode in (0,1):
        baseline=run(mode,100,chip_factory=ReferenceChip,disturbance_sign=1)
        for sign in (0,-1,1):
            params={} if not sign else dict(gain_error=sign*.1,phase_error=sign*.08,saturation=.3,noise_rms=.003)
            factory=lambda **kw:ImpairedChip(frontend=params,**kw)
            row=run(mode,100,chip_factory=factory,disturbance_sign=1)
            if not sign:assert row['adc_sha256']==baseline['adc_sha256']
            else:assert row['adc_sha256']!=baseline['adc_sha256']
            assert row['reference_metrics']['frontend']['samples']==row['rf_samples_each_direction']
            rows.append(row)
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Impairments act after RX filtering at the ADC frontend; not RF LNA/mixer compression or blocker response.',
        'Independent per-sample Gaussian noise is assumed integrated ADC input noise, not a continuous noise PSD.',
        'Reported relative RMS error is pre-reference frontend distortion, not calibrated modem EVM.',
        'Illustrative values and one fixed seed do not establish GF180 capability, uncertainty bounds or yield.'])
    (P/'evidence/connected-receiver-impairments.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six sustained receiver-impairment cases and analytic/noise controls')

if __name__=='__main__':main()
