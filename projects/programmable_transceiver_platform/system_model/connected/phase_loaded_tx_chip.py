"""Experimental managed loaded network with event-aligned autonomous LO phase."""
import copy,math
from loaded_tx_chip import LoadedTxChip
from rf_phase_forcing import advance_phase

class PhaseLoadedTxChip(LoadedTxChip):
    def __init__(self,phase_step_s=1e-9,**kwargs):
        if not math.isfinite(phase_step_s) or phase_step_s<=0:raise ValueError('Invalid phase step')
        self.phase_step=phase_step_s;self.phase_steps=0;self.phase_residual=0.;self.phase_events=0
        super().__init__(**kwargs)
    def _drive_loaded_network(self,time,terms):
        start=self.loaded_tx.network.time
        if self.rf_pll.time>start:
            raise ValueError('Oscillator history already advanced past loaded network')
        original=copy.copy(self.rf_pll)
        future=copy.copy(original);future.advance(time)
        events=sorted(set(t for t,current in future.transitions if start<t<time))
        carrier=self.loaded_tx.network.omega/(2*math.pi)
        def phase(t):
            trial=copy.copy(original);trial.advance(t)
            return 2*math.pi*(trial.output_phase_cycles-carrier*t)+self.rf_tx_phase
        result=advance_phase(self.loaded_tx,time,terms,phase,self.phase_step,events)
        self.phase_steps+=result['steps'];self.phase_events+=len(events)
        self.phase_residual=max(self.phase_residual,result['max_midpoint_phase_error'])
