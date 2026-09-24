"""Selected full-chip mathematical composition and its declared assumptions.

This is a conditional design model, not a physically qualified implementation.
All canonical scenarios must construct this composition rather than substitute
an older class or disable the coupled analog owner.
"""
import hashlib
import json
from check_contract import CONTRACT, check_protocol_profiles
from fast_exclusive_engine import IntegratedTransceiverChip
from shared_supply_lifecycle import DomainSupply
from oscillator_noise import FrequencyNoise
from host_bank_supply import LimitedHostBankSupply
from protocol_service import ProtocolService

MODEL_ID = 'exclusive-coupled-domains-host-v1'
DOMAINS = ('CORE', 'HOST_A', 'HOST_B', 'WIRE_A', 'WIRE_B', 'RF', 'PLL')
BACKGROUND_A = {
    'none': (.020, .002, .002, 0., 0., 0., .008),
    'rf':   (.020, .002, .002, 0., 0., .012, .008),
    'wire': (.020, .002, .002, 0., .005, 0., .008),
}


def protocol_requirements():
    return check_protocol_profiles(json.loads(CONTRACT.read_text()))


def parameters():
    return dict(protocol_profiles=protocol_requirements(),
        contract_sha256=hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),model_id=MODEL_ID, domains=list(DOMAINS), nominal_v=3.3,
        feed_r_ohm=2., decoupling_f=100e-12, common_return_r_ohm=.1,
        minimum_supply_v=2.5, background_current_a=BACKGROUND_A,
        host_output_capacitance_f=10e-12, host_pullup_r_ohm=100.,
        host_pulldown_r_ohm=80., host_pullup_limit_a=.010,
        host_pulldown_limit_a=.012, host_internal_edge_charge_c=7e-12,
        host_internal_decay_s=.5e-9, input_edge_charge_c=50e-15,
        rf_supply_sensitivity_hz_per_v=1e6, wire_supply_sensitivity_hz_per_v=1e5,
        reference_source_limit_a=150e-6, reference_sink_limit_a=150e-6,
        bias_settle_s=2e-6, host_ddr_clocks_hz=[125e6,156.25e6],
        assumptions=[
            'Background currents are provisional residual loads, not a complete circuit power estimate.',
            'Mode loads switch at ownership change; bias settling is a guard, not a characterized current ramp.',
            'Input receiver switching still uses an unqualified 50 fC disturbance; output charging is explicit.',
            'Pad delays, external receiver timing, package inductance and substrate coupling remain unqualified.',
            'Separate RF and wired synthesizer instances; physical synthesizer sharing is not implemented.',
            '150 MHz exclusive transport remains a separate candidate, not an installed model option.'])


def make_chip(*, rf_noise_rms_hz=0., protocol=None, rf_solver_method="Radau"):
    """One physical-resource composition; scenarios may vary declared noise."""
    profiles = protocol_requirements()
    if protocol is not None:
        selected = next((p for p in profiles if p['id'] == protocol), None)
        if selected is None:
            raise ValueError('Unknown protocol profile')
        if selected["model_status"] != "phy_primitives":
            raise NotImplementedError(f"{protocol}: no executable profile primitives")
    noise=FrequencyNoise.seeded(rf_noise_rms_hz,seed=839)
    host=LimitedHostBankSupply([3.3]*7,[2.]*7,[100e-12]*7,.1,
        [1]*5+[2]*6,[10e-12]*11,[100.]*11,[80.]*11,
        pullup_limit_a=[.010]*11,pulldown_limit_a=[.012]*11,
        rising_charge_c=[7e-12]*11,falling_charge_c=[7e-12]*11,
        switching_tau_s=.5e-9,minimum_supply_v=[2.5]*7)
    holder={}
    def load(time,voltage):
        return BACKGROUND_A[holder['chip'].active_engine]
    c=IntegratedTransceiverChip(coupled_analog=True,rf_solver_method=rf_solver_method,
        domain_supply=DomainSupply(DOMAINS,[3.3]*7,[2.]*7,[100e-12]*7,.1),
        domain_minimum_v=[2.5]*7,domain_load=load,host_bank=host,
        charge_per_transition=50e-15,return_charge_per_transition=0.,
        rf_hz_per_v=1e6,wire_hz_per_v=1e5,
        reference_source_limit_a=150e-6,reference_sink_limit_a=150e-6,
        bias_settle_s=2e-6,watchdog_s=1e-3,tx_relative_gain=True,
        rf_noise_rms_hz=rf_noise_rms_hz,noise_seed=839,
        coarse_noise_bound_hz=noise.bound_hz)
    holder['chip']=c
    c.protocol_requirements=profiles
    c.protocol_service=ProtocolService(c,profiles)
    if protocol is not None:c.protocol_service.select(protocol)
    c.model_id=MODEL_ID
    return c
