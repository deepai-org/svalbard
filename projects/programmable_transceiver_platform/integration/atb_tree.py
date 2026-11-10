"""Complete extracted ATB tree with the retained provider analog pad cells.

Every legal code has one physical leaf. Node ports must be bound to the chip's
actual source nets by the parent assembly; this macro adds no node stimulus.
"""
import json
from pathlib import Path

from check_chip_power import PROJECT, instance, ports


def build(read, island_pex, provider):
    controls = json.loads(read(PROJECT/'spec/debug-controls.json'))
    nodes = [n for n in controls['atb_nodes'] if n.get('hardware', True)]
    groups = controls['atb_groups']
    models = {}
    for cell in ('atb_leaf_s', 'atb_leaf_f', 'atb_grp', 'atb_pad'):
        path = Path(island_pex)/'pexd'/cell/(cell+'.pex.spice')
        models[cell] = read(path)
        assert ports(models[cell], cell+'_flat'), 'Missing extracted cell'
    pins = ['VDD', 'VSS', 'ATB0', 'ATB1']
    bindings = {}
    for node in nodes:
        pins.append('NODE_'+node['name'])
    body = []
    leaves = []
    for bus in (0, 1):
        eligible = [n for n in nodes if bus == 1 or n['force'] != 'sense_only']
        code_to_group = {}
        for index, group in enumerate(groups[f'atb{bus}']):
            assert len(group['codes']) <= groups.get('max_leaves_per_group', 12), 'Local bus exceeds qualified leaf load'
            for code in group['codes']:
                assert code not in code_to_group, 'Duplicate physical leaf code'
                code_to_group[code] = index
        assert set(code_to_group) == {n['code'] for n in eligible}, 'Missing/extra physical leaf code'
        for node in eligible:
            code = node['code']
            pin = f'ATB{bus}_SW_{code-1}'
            pins.append(pin)
            bindings[pin] = f'atb{bus}_sw[{code-1}]'
            cell = 'atb_leaf_f' if bus == 0 else 'atb_leaf_s'
            connections = dict(NODE='NODE_'+node['name'], BUS=f'LOCAL{bus}_{code_to_group[code]}',
                               SEL=pin, VDD='VDD', VSS='VSS')
            body.append(instance(f'Xleaf{bus}_{code}', cell+'_flat', models[cell], connections))
            leaves.append(dict(bus=bus, code=code, name=node['name'], group=code_to_group[code],
                               cell=cell+'_flat', node_port=connections['NODE'], select_port=pin))
        for index, group in enumerate(groups[f'atb{bus}']):
            pin = f'ATB{bus}_GRP_{index}'
            pins.append(pin)
            bindings[pin] = f'atb{bus}_grp[{index}]'
            body.append(instance(f'Xgroup{bus}_{index}', 'atb_grp_flat', models['atb_grp'],
                                 dict(NODE=f'LOCAL{bus}_{index}', BUS=f'GLOBAL{bus}', SEL=pin, VDD='VDD', VSS='VSS')))
        pin = f'ATB{bus}_EN'
        pins.append(pin)
        bindings[pin] = f'atb{bus}_en'
        body.append(instance(f'Xpad_switch{bus}', 'atb_pad_flat', models['atb_pad'],
                             dict(PAD=f'ATB{bus}', BUS=f'GLOBAL{bus}', SEL=pin, VDD='VDD', VSS='VSS')))
        body.append(instance(f'Xprovider{bus}', 'gf180mcu_fd_io__asig_5p0', provider,
                             dict(ASIG5V=f'ATB{bus}', DVDD='VDD', DVSS='VSS', VDD='VDD', VSS='VSS')))
    text = '\n'.join(models.values())+'\n.subckt pt_atb_tree '+' '.join(pins)+'\n'
    text += '\n'.join(body)+'\n.ends pt_atb_tree\n'
    return dict(text=text, pins=pins, control_bindings=bindings, leaves=leaves,
                sense_leaves=sum(n['bus'] == 1 for n in leaves),
                force_leaves=sum(n['bus'] == 0 for n in leaves),
                group_sizes={f'atb{bus}': [len(g['codes']) for g in groups[f'atb{bus}']] for bus in (0, 1)},
                scope='extracted complete tree; parent must bind node/control ports and qualify assembly')
