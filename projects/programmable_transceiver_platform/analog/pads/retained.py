"""Shared first-pass host-cell binding and retained supply-pad inventory."""
import json
from design import PROJECT,resolve


def binding():
    architecture=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    contract=json.loads((PROJECT/'spec/contract.json').read_text())
    host=architecture['blocks']['hostio']['parameters']
    if host['default_strength']!='bi_t PDRV01 SL0 engineering candidate':
        raise ValueError('Update retained-cell binding for the selected host setting')
    sites=contract['assembly_policy']['candidate_signal_sites']
    outputs={signal:site for signal,site in sites.items() if signal.startswith('D2H_') or signal=='HOST_MISO'}
    powers=[s for ordered in resolve()['provider_inventory'].values() for s in ordered
            if s.startswith(('dvdd_pads[','dvss_pads[','vdd_pads[','vss_pads['))]
    return dict(status='first_pass_candidate_not_full_rate_or_power_off_qualification',
        output_master='gf180mcu_fd_io__bi_t',output_sites=outputs,
        settings=dict(PDRV0=0,PDRV1=1,SL=0,CS=0,IE=0),drive_ma=12,
        supply_sites=powers,host_output=contract['physical_services']['host_output'],
        provider_foundry_rail_policy='VDD=DVDD and VSS=DVSS in the pinned provider top-level; logical domains are not separate external rails',
        limitations=['Native clock-input cell at clk_pad cannot implement D2H_D[0]; use the selected bidirectional output candidate at that bond site.',
                     'Host inputs/reset retain native input-capable cells; their upper clamps do not imply unpowered tolerance.',
                     'Native supply-pad circuits and finite external bonds do not include distributed on-die ring impedance.'])
