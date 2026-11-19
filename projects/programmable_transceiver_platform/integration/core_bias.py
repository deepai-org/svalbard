"""Per-chip core bias: reference chain, distribution root and the island bias banks.

One generator, one composite per chip (decision D8):  build(read, chip) with chip 'rf' or 'wired' returns
the netlist of `pt_core_bias_<chip>`.

Both chips carry the same always-on reference chain on core VDD: biasgen (patched), bandgap, `pt_bias_vref`
and `pt_bias_root` (five switched 10 uA trunk legs). Each trunk feeds one island bank whose PMOS diode and
mirrors sit on that island's rail (a bank must share the rail of every consumer tap it serves: README
'Conditions of use'). One exception: on pt_rf the rf_rx bank also feeds txmix_i/q and rfdriver on RAIL_rf_tx
(the root has five legs, all used on pt_rf). Both rails switch on the same enable (rf group, island_on[1]) and
each consumer is an NMOS diode, so a dead rf_tx rail only takes up to 10 uA per output into an unpowered diode. Banks are the qualified `pt_bias_bank<N>` cells; a bank with fewer consumers than
outputs has the spare outputs disabled (EN = VSS), drains open.

Trunk legs of `pt_bias_root` are named RF, CONV, PLL, WIRE, DEBUG; the table TRUNKS says which leg serves
which island on each chip. Two trunks of one enable group share one enable gate (dist_en AND island_on).

No ideal currents, voltages or loads live inside this assembly. The parent binds each output to its actual
consumer and each EN_<consumer> to that consumer's effective enable. Register controls are identified by
generated bit index.
"""
import hashlib
import json
from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parents[1]

CHIPS = ('rf', 'wired')

# trunk name: (root leg, enable group (ON_<group>), dist_en field suffix, bank size, consumers, ATB code or None)
TRUNKS = {
    'rf': {
        'rf_rx': ('RF', 'rf', 'rf', 8, ['lna', 'rxmix_i', 'rxmix_q', 'bbfilter_i', 'bbfilter_q',
                                         'txmix_i', 'txmix_q', 'rfdriver'], 14),
        'conv': ('CONV', 'conv', 'conv', 5, ['adc_i', 'adc_q', 'dac_i', 'dac_q', 'refbuf'], 35),
        'pll': ('PLL', 'pll', 'pll', 3, ['pll_ring_tx', 'pll_ring_rx', 'cdr'], 29),
        'lo': ('WIRE', 'rf', 'rf', 3, ['qvco', 'lo_pfdcp'], None),
        'debug': ('DEBUG', 'debug', 'debug', 3, ['bb_tap_i', 'bb_tap_q'], 56),
    },
    'wired': {
        'pll': ('PLL', 'pll', 'pll', 3, ['pll_ring_tx', 'pll_ring_rx', 'cdr'], 29),
        'wired_rx': ('WIRE', 'wired', 'wire', 3, ['ctle', 'detect'], 22),
        'wired_tx': ('RF', 'wired', 'wire', 3, ['wiredtx', 'hsbias'], None),
        'debug': ('DEBUG', 'debug', 'debug', 3, ['bb_tap_wmon'], 56),
    },
}
ROOT_LEGS = ('RF', 'CONV', 'PLL', 'WIRE', 'DEBUG')


def ports(text, cell):
    text = re.sub(r'\n\+\s*', ' ', text)
    return next(line.split()[2:] for line in text.splitlines()
                if line.lower().startswith('.subckt '+cell.lower()+' '))


def instance(label, cell, text, connections):
    pins = ports(text, cell)
    if set(pins) != set(connections):
        raise ValueError(f'{cell} pin mismatch: {set(pins)^set(connections)}')
    return f'{label} '+' '.join(connections[p] for p in pins)+' '+cell


def top_name(chip):
    return 'pt_core_bias_'+chip


def trk_pin(trunk):
    return 'TRK_'+trunk.upper()


def build(read, chip):
    assert chip in CHIPS, chip
    trunks = TRUNKS[chip]
    top = top_name(chip)
    model_dir = PROJECT/'integration/models/core_bias'
    manifest = json.loads(read(model_dir/'manifest.json'))
    models = []
    cells = {}
    for name, info in manifest['models'].items():
        source = read(model_dir/info['file'])
        assert hashlib.sha256(source.encode()).hexdigest() == info['sha256'], f'Changed qualified model: {name}'
        if name == 'bandgap':
            # Same documented Magic-recognition correction as sim_bandgap.py.
            source = source.replace('pnp_10p00x00p42', 'pnp_05p00x05p00')
        cell = 'gf180mcu_ocd_ip__'+('biasgen' if name == 'biasgen_patched' else 'bandgap')
        cells[name] = (source, cell)
        models.append(source)
    distribution = PROJECT/'analog/core_support/distribution/generated'
    for cell in ['pt_bias_root', 'pt_bias_vref']+[f'pt_bias_bank{n}' for n in sorted({t[3] for t in trunks.values()})]:
        source = read(distribution/(cell+'.ext.spice'))
        cells[cell] = (source, cell)
        models.append(source)
    # The DRC/LVS-qualified extracted AND leaf, including its extra exported
    # extraction nodes (private to each instance).
    glue = read(PROJECT/'analog/bringup_control/generated/pt_wtx_fallback_control.ext.spice')
    match = re.search(r'^\.subckt bringup_and\b.*?^\.ends[^\n]*', glue, re.M | re.S)
    assert match
    glue = match.group()+'\n'
    models.append(glue)
    mapping = json.loads(read(PROJECT/'spec/register-map.json'))
    fields = {f['name']: f for f in mapping['fields']}
    groups = sorted({t[1] for t in trunks.values()})
    dists = sorted({t[2] for t in trunks.values()})
    pin_list = ['VDD', 'VSS']+[f'RAIL_{t}' for t in trunks]+[f'ON_{g}' for g in groups]
    bindings = {}
    field_pins = {}
    for prefix in ('core.biasgen', 'core.refchain'):
        for field in fields.values():
            name = field['name']
            if not name.startswith(prefix+'.'):
                continue
            if name.startswith('core.refchain.dist_en_') and name.rsplit('_', 1)[1] not in dists:
                continue  # trunk field of the other chip: not stored there (spec/chips.json)
            assert field['bus'] == 'debug' and field['bus_lsb'] is not None, name
            width = field.get('bus_bits', field['bits'])
            # Thermometer decoding exports 16 bits from the five-bit trim.
            if name == 'core.refchain.bgap_trim':
                width = 16
            names = []
            for bit in range(width):
                pin = 'C_'+name.replace('.', '_')+(f'_{bit}' if width > 1 else '')
                pin_list.append(pin)
                bindings[pin] = f'debug_cfg[{field["bus_lsb"]+bit}]'
                names.append(pin)
            field_pins[name] = names

    def scalar(name):
        assert len(field_pins[name]) == 1
        return field_pins[name][0]
    consumers = {t: v[4] for t, v in trunks.items()}
    for trunk, names in consumers.items():
        for consumer in names:
            pin_list += ['EN_'+consumer, 'BIAS_'+consumer]
    # Codes 2/3: the master voltage references (VREF0 -> refbuf.VREF0, VCM -> adc VCM), from pt_bias_vref.
    observation = {1: 'ROOT_REF', 2: 'VREF0', 3: 'VCM', 55: 'VBG', 57: 'IDAC1'}
    observation.update({v[5]: trk_pin(t) for t, v in trunks.items() if v[5] is not None})
    observation = dict(sorted(observation.items()))
    trunk_nodes = [trk_pin(t) for t in trunks]
    pin_list += ['ROOT_REF', 'VREF0', 'VCM', 'VBG', 'IDAC1']+trunk_nodes+['VGEN_SOURCE', 'VGEN_SINK1', 'VGEN_SINK2']
    body = []
    control_instances = []

    def and_gate(label, a, b, y):
        connect = dict(A=a, B=b, Y=y, VDD='VDD', VSS='VSS')
        for index, pin in enumerate(ports(glue, 'bringup_and')):
            if pin not in connect:
                connect[pin] = label+'_private_'+str(index)
        body.append(instance(label, 'bringup_and', glue, connect))
        control_instances.append(dict(instance=label, a=a, b=b, y=y))
    and_gate('Xfine_guard', scalar('core.biasgen.ref_sel_fine'), scalar('core.biasgen.ref_sel_coarse'), 'FINE_EFFECTIVE')
    source, cell = cells['biasgen_patched']
    connect = dict(ena=scalar('core.biasgen.ena'), ref_in='VDD', dvdd='VDD', avdd='VDD',
                   dvss='VSS', vbg='VBG', ref_sel_vbg=scalar('core.biasgen.ref_sel_vbg'),
                   ref_sel_coarse=scalar('core.biasgen.ref_sel_coarse'), ref_sel_fine='FINE_EFFECTIVE',
                   idac1_source_ibias='IDAC1', idac2_source_ibias='ROOT_REF',
                   voltgen_source_ibias='VGEN_SOURCE', voltgen_sink1_ibias='VGEN_SINK1',
                   voltgen_sink2_ibias='VGEN_SINK2', bandgap_sink1_ibias='BANDGAP_IBIAS2',
                   bandgap_sink2_ibias='BANDGAP_IBIAS1')
    for name in ('idac1_source', 'idac2_source', 'bandgap_sink1', 'bandgap_sink2',
                 'voltgen_source', 'voltgen_sink1', 'voltgen_sink2'):
        for bit, pin in enumerate(field_pins['core.biasgen.'+name]):
            connect[f'{name}[{bit}]'] = pin
    body.append(instance('Xbiasgen', cell, source, connect))
    source, cell = cells['bandgap']
    connect = dict(dvdd='VDD', dvss='VSS', vbg='VBG', ena=scalar('core.refchain.bgap_ena'),
                   ibias1_250n='BANDGAP_IBIAS1', ibias2_1u='BANDGAP_IBIAS2')
    connect.update({f'trim[{bit}]': pin for bit, pin in enumerate(field_pins['core.refchain.bgap_trim'])})
    body.append(instance('Xbandgap', cell, source, connect))
    # Root: unused legs are disabled and their drains tied to VSS.
    root = dict(VSS='VSS', ROOT_REF='ROOT_REF')
    for leg in ROOT_LEGS:
        root['EN_'+leg] = 'VSS'
        root['TRK_'+leg] = 'VSS'
    gated = {}
    for trunk, (leg, group, dist, size, names, _code) in trunks.items():
        key = (dist, group)
        if key not in gated:
            gated[key] = f'TRUNK_EN_{group}'
            and_gate(f'Xtrunk_{group}', scalar('core.refchain.dist_en_'+dist), 'ON_'+group, gated[key])
        root['EN_'+leg] = gated[key]
        root['TRK_'+leg] = trk_pin(trunk)
        bank = dict(VDD='RAIL_'+trunk, VSS='VSS', TRK=trk_pin(trunk))
        for index in range(size):
            if index < len(names):
                consumer = names[index]
                bank['OUT'+str(index)] = 'BIAS_'+consumer
                and_gate('Xoutput_'+consumer, 'EN_'+consumer, 'ON_'+group, 'BANK_EN_'+consumer)
                bank['EN'+str(index)] = 'BANK_EN_'+consumer
            else:
                # spare output: disabled, drain left on a private net (a VSS tie beside a used output
                # brings a supply route between two signal pins of the bank)
                bank['OUT'+str(index)] = f'SPARE_{trunk}_{index}'
                bank['EN'+str(index)] = 'VSS'
        source, cell = cells['pt_bias_bank'+str(size)]
        body.append(instance('Xbank_'+trunk, cell, source, bank))
    source, cell = cells['pt_bias_root']
    body.append(instance('Xroot', cell, source, root))
    source, cell = cells['pt_bias_vref']
    body.append(instance('Xvref', cell, source, dict(VDD='VDD', VSS='VSS', VBG='VBG', VREF0='VREF0', VCM='VCM')))
    assert len(set(pin_list)) == len(pin_list)
    text = '\n'.join(models)+f'\n.subckt {top} '+' '.join(pin_list)+'\n'
    text += '\n'.join(body)+f'\n.ends {top}\n'
    return dict(top=top, chip=chip, text=text, pins=pin_list, control_bindings=bindings, field_pins=field_pins,
                consumers=consumers, trunks={t: dict(leg=v[0], group=v[1], dist_en=v[2], bank=f'pt_bias_bank{v[3]}',
                                                     rail='RAIL_'+t, trk=trk_pin(t), atb_code=v[5])
                                             for t, v in trunks.items()},
                observation_bindings=observation, control_instances=control_instances,
                notes=['Parent connects real consumer IBIAS pins and effective enables.',
                       'Each bank sits on the rail of its consumers; spare bank outputs are disabled, drains open.',
                       'Unused root legs are disabled with their drains on VSS.',
                       'Extracted reference models retain all capacitances; PNP name corrected as documented.',
                       'VREF0 (5/6 VBG) and VCM (VDD/2) come from the passive pt_bias_vref on core VDD.'])


if __name__ == '__main__':
    import sys
    for chip in (sys.argv[1:] or CHIPS):
        core = build(lambda p: Path(p).read_text(), chip)
        print(core['top'], len(core['pins']), 'pins,', core['text'].split(f'.subckt {core["top"]} ')[1].count('\nX'), 'instances,',
              len(core['control_instances']), 'gates; ATB', core['observation_bindings'])
        print('master', core['top'], 'inline', ' '.join(core['pins']))
