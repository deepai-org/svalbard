"""Independent reproducible VCO frequency-noise sources in the connected chip."""
from oscillator_noise import FrequencyNoise
from oscillator_supply_lifecycle import OscillatorSupplyChip


class NoisyOscillatorChip(OscillatorSupplyChip):
    def __init__(self,rf_noise_rms_hz=0.,wire_noise_rms_hz=0.,noise_seed=830,**kwargs):
        self.rf_noise=FrequencyNoise.seeded(rf_noise_rms_hz,seed=noise_seed)
        self.wire_noise=FrequencyNoise.seeded(wire_noise_rms_hz,seed=noise_seed+1)
        super().__init__(**kwargs)
        self.rf_pll.set_noise(self.time,self.rf_noise)
        self.install_segment(self.rf_pll.frequency_hz-self.rf_carrier,check=False)

    def make_serializer(self,time):
        serializer=super().make_serializer(time)
        # Keep the same absolute-time noise realization across digital resets.
        self.wire_pll.set_noise(time,self.wire_noise)
        return serializer

    def reference_metrics(self):
        result=super().reference_metrics()
        result['vco_frequency_noise']=dict(rf_lines=self.rf_noise.tones,wire_lines=self.wire_noise.tones,
            rf_bound_hz=self.rf_noise.bound_hz,wire_bound_hz=self.wire_noise.bound_hz)
        return result
