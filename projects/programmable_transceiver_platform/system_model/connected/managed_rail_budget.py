"""Controlled driver supply-impedance experiment; no clock-limit changes."""
import json,math
from chip_model import P
from managed_dense_reference import ManagedDenseReferenceChip

class ManagedRailBudgetChip(ManagedDenseReferenceChip):
    def __init__(self,driver_rail_resistance_ohm=20.,**kwargs):
        if not math.isfinite(driver_rail_resistance_ohm) or driver_rail_resistance_ohm<=0:
            raise ValueError('Invalid experimental driver rail impedance')
        # Nonbinding limits reproduce the older unlimited-reference baseline;
        # this isolates rail impedance from the separate 150uA candidate.
        kwargs.setdefault('reference_source_limit_a',1.)
        kwargs.setdefault('reference_sink_limit_a',1.)
        super().__init__(**kwargs)
        self.loaded_tx.driver.r=driver_rail_resistance_ohm
        self.first_fault_written=False
    def quiesce(self,time,reason):
        if not self.first_fault_written:
            self.first_fault_written=True
            pll=self.rf_pll;d=self.loaded_tx.driver
            report=dict(time_s=time,reason=reason,state=self.state,rail_resistance_ohm=d.r,
                driver_rail_v=d.rail_v,reference_v=self.adc_reference.voltage,
                rf_frequency_hz=pll.frequency_hz,rf_error_cycles=pll.error,
                frequency_error_at_reference_hz=pll.frequency_hz/pll.divider-pll.reference_hz,
                lock_frequency_limit_hz=pll.lock_frequency,lock_phase_limit=pll.lock_phase,
                reference_present=pll.present,lock_history=self.rf_lock_history[-16:],
                preceding_events=self.events[-12:])
            name=f'rail-budget-{d.r:g}ohm-first-fault.json'
            (P/'evidence'/name).write_text(json.dumps(report,indent=2)+'\n')
            print('FIRST FAULT',report,flush=True)
        return super().quiesce(time,reason)
