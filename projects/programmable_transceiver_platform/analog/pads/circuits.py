"""Parameterized device graph shared by SPICE and physical generators.

Sizes are first-pass implementation choices, not achieved electrical budgets.
Core bias/control inputs are explicit: no ideal current source is hidden inside
the pad cell. ESD snapback survival is not established by the ordinary PDK model.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import json
from design import resolve


@dataclass(frozen=True)
class Resistor:
    name: str
    nodes: tuple
    model: str
    w_um: float
    l_um: float

    def spice(self):
        return (f"X{self.name} {' '.join(self.nodes)} {self.model} "
                f"r_width={self.w_um}u r_length={self.l_um}u")


@dataclass(frozen=True)
class Mos:
    name: str
    nodes: tuple
    model: str
    w_um: float
    l_um: float

    def spice(self):
        # The selected single-finger PCells extract 0.44 um diffusion length
        # on each side. Do not use the PDK's zero-area defaults (which omit
        # junction loading). Custom contacted DSS geometry has explicit
        # ballast extensions. Their dimensions alone do not qualify ESD.
        drain, source = (4.22,.72) if self.model.endswith('_dss') else (.44,.44)
        sab = ' d_sab=3.78u s_sab=0.28u' if self.model.endswith('_dss') else ''
        return (f"X{self.name} {' '.join(self.nodes)} {self.model} w={self.w_um}u l={self.l_um}u nf=1 m=1"
                f" ad={self.w_um*drain}p as={self.w_um*source}p"
                f" pd={2*(self.w_um+drain)}u ps={2*(self.w_um+source)}u{sab}")


@dataclass
class Circuit:
    name: str
    ports: list
    devices: list
    requirements: dict
    limitations: list

    def spice(self):
        return '\n'.join([
            '* Generated from circuits.py; external bias/control circuitry is explicit.',
            '* No ESD survival claim. Zero ideal pad capacitance is added to device capacitance.',
            '.subckt ' + self.name + ' ' + ' '.join(self.ports),
            *[d.spice() for d in self.devices],
            '.ends ' + self.name, '',
        ])


def wired_transmit(*, protection_units=2, protection_width_um=16.,
                   steering_units=8, steering_width_um=20., tail_width_um=20.,
                   cascode_units=2, cascode_width_um=16., tail_units=2, serial_tail_units=None,
                   termination_bleed_width_um=2., termination_bleed_length_um=2.):
    """Driver/detection branches and selectable source termination.

    Generation-time sizing knobs are not runtime protocol profiles.

    Per-leg gate controls use complementary pairs supplied by the serializer.
    Biases are supplied by the core current DACs. Reset/power-down must discharge
    bias and selector gates through the control interface; that interface is
    exercised separately rather than represented by an ideal internal reset.
    """
    if any(type(n) is not int or n < 1 for n in (protection_units, steering_units, cascode_units, tail_units)):
        raise ValueError('Positive integer unit counts required')
    if any(not 0.8 <= w <= 20 for w in (protection_width_um, steering_width_um, tail_width_um, cascode_width_um)):
        raise ValueError('First-pass unit width range is 0.8..20 um')
    if not (.8<=termination_bleed_width_um<=20 and .8<=termination_bleed_length_um<=20):
        raise ValueError('Termination discharge geometry must fit the resistor PCell reservation')
    if serial_tail_units is not None and (type(serial_tail_units) is not int or serial_tail_units<1):
        raise ValueError('Positive integer serial tail unit count required')
    required = resolve()['families']['wired_transmit']
    ports = ['PAD_P', 'PAD_N', 'VDD', 'VSS', 'CASCODE',
             'MAIN_P', 'MAIN_N', 'MAIN_BIAS', 'POST_P', 'POST_N', 'POST_BIAS',
             'TMDS_P', 'TMDS_N', 'TMDS_BIAS', 'DETECT_ENABLE', 'DETECT_PBIAS',
             'TERM_ENABLE', 'TERM_VCM']
    devices = []
    def mos(name, d, g, s, b, model='nfet_03v3', w=12., l=.28):
        devices.append(Mos(name, (d, g, s, b), model, w, l))
    for leg in ('P', 'N'):
        for unit in range(protection_units):
            mos(f'ESD_{leg}_{unit}', f'PAD_{leg}', 'VSS', 'VSS', 'VSS',
                'nfet_06v0_dss', protection_width_um, .6)
    # The three steering branches share each unit's output cascodes. This
    # removes duplicated pad-connected diffusion while retaining independent
    # selectors/tails and the common analog cascode bias interface.
    for unit in range(steering_units):
        for leg in ('P','N'):
            for finger in range(cascode_units):
                mos(f'CAS_{leg}_{unit}_{finger}',f'PAD_{leg}','CASCODE',f'SUM_{leg}_D_{unit}',
                    'VSS','nfet_06v0',cascode_width_um,.7)
    for branch in ('MAIN', 'POST', 'TMDS'):
        for unit in range(steering_units):
            tail = f'{branch}_TAIL_{unit}'
            units=serial_tail_units if branch in ('MAIN','POST') and serial_tail_units is not None else tail_units
            for finger in range(units):
                mos(f'{branch}_TAIL_{unit}_{finger}', tail, f'{branch}_BIAS', 'VSS', 'VSS',
                    w=tail_width_um, l=1.)
            for leg in ('P', 'N'):
                internal = f'SUM_{leg}_D_{unit}'
                mos(f'{branch}_{leg}_SEL_{unit}', internal, f'{branch}_{leg}', tail, 'VSS',
                    w=steering_width_um)
    # Supply-powered enable buffers with passive discharge. These do not
    # substitute for the still-required reset/brownout supervisor.
    for control in ('DETECT', 'TERM'):
        for suffix, incoming, outgoing in (
                ('INV', control+'_ENABLE', control+'_ENABLE_B'),
                ('BUF', control+'_ENABLE_B', control+'_ENABLE_LOCAL')):
            # Slow control nodes retain charge during rail and mode changes.
            mos(control+'_'+suffix+'_N', outgoing, incoming, 'VSS', 'VSS',
                'nfet_06v0', 2., .7)
            mos(control+'_'+suffix+'_P', outgoing, incoming, 'VDD', 'VDD',
                'pfet_06v0', 4., .55)
        previous = control+'_ENABLE_LOCAL'
        for index in range(8):
            following = 'VSS' if index == 7 else f'{control}_BLEED_{index}'
            devices.append(Resistor(f'{control}_BLEED_{index}',
                (previous, following, 'VSS'), 'ppolyf_u_1k', 1., 12.5))
            previous = following
    # Common-mode source belongs to the attached bias/regulator block. Its
    # finite impedance and current capability must be included at integration.
    # These are candidate dimensions; measure R + nonlinear switch resistance.
    for leg in ('P', 'N'):
        node = f'TERM_{leg}_R'
        devices.append(Resistor(f'TERM_{leg}', (f'PAD_{leg}', node, 'VSS'),
                                'ppolyf_s', 1., 1.8))
        for unit in range(8):
            mos(f'TERM_{leg}_SW_{unit}', node, 'TERM_ENABLE_LOCAL',
                'TERM_VCM', 'VSS', w=20., l=.28)
    for leg in ('P', 'N'):
        injection = f'DETECT_{leg}_I'
        mos(f'DETECT_{leg}_SOURCE', injection, 'DETECT_PBIAS', 'VDD', 'VDD',
            'pfet_03v3', 4., 2.)
        mos(f'DETECT_{leg}_ISOLATE', injection, 'DETECT_ENABLE_LOCAL', f'PAD_{leg}', 'VSS',
            'nfet_06v0', 4., .7)
    # An always-connected return for stored termination-buffer charge. It
    # does not depend on the core supervisor surviving supply collapse.
    # Its continuous current must be supplied by the local termination buffer.
    devices.append(Resistor('TERM_DISCHARGE',('TERM_VCM','VSS','VSS'),
                            'ppolyf_u_1k',termination_bleed_width_um,termination_bleed_length_um))
    return Circuit('pad_wired_transmit', ports, devices, required, [
        'Grounded-gate drain-SAB devices are protection candidates, not a qualified ESD clamp.',
        'Sense comparator uses the same PAD_P/N nodes; comparator and core DACs are external to this cell.',
        'Source termination includes switched resistors and a passive TERM_VCM discharge resistor; impedance trim and the physical current-limited buffer remain unimplemented.',
        'Detection enable has a local supply-powered buffer and passive discharge; reset and brownout supervision remain unimplemented.',
        'Protection capacitance, cascode compliance and driver current must be measured, not assumed.',
    ])


def analog_port(family, *, protection_units=2, protection_width_um=16.):
    """Dedicated RF/reference pads; core connects to the same PAD_P/N nets.

    There is no signal-path mux or switched-off upper-rail diode. The reference
    bias is a real segmented PDK resistor. RF bias belongs to the attached LNA
    or driver, so it is not duplicated in the pad. Matching/coupling parts are
    external and must remain connected through the lifecycle benches.
    """
    if family not in ('reference_clock','rf_receive','rf_transmit'):
        raise ValueError('Dedicated analog pad family required')
    if type(protection_units) is not int or protection_units<1:
        raise ValueError('Positive integer protection count required')
    if not .8<=protection_width_um<=20:
        raise ValueError('Protection unit width must be 0.8..20 um')
    required=resolve()['families'][family]
    devices=[]
    ports=['PAD_P','PAD_N','VSS']
    for leg in ('P','N'):
        for unit in range(protection_units):
            devices.append(Mos(f'ESD_{leg}_{unit}',(f'PAD_{leg}','VSS','VSS','VSS'),
                               'nfet_06v0_dss',protection_width_um,.6))
    if family=='reference_clock':
        ports.append('VCM')
        target=required['electrical_parameters']['input_r_ohm']
        # Geometry uses the installed nominal 1 kohm/square resistor. Actual
        # PDK end/width corrections and bias dependence are measured in SPICE.
        segments=8; width=1.; length=target/segments/1000*width
        if not 1<=length<=20:
            raise ValueError('Reference bias needs a different segment count')
        for leg in ('P','N'):
            previous=f'PAD_{leg}'
            for index in range(segments):
                following='VCM' if index==segments-1 else f'BIAS_{leg}_{index}'
                devices.append(Resistor(f'BIAS_{leg}_{index}',(previous,following,'VSS'),
                                        'ppolyf_u_1k',width,length))
                previous=following
    return Circuit('pad_'+family,ports,devices,required,[
        'PAD_P/N are both bond and core-facing signal nets; the attached front end is outside this cell.',
        'External coupling/matching and the attached core load are retained bench networks, not hidden ideal isolation.',
        'Protection geometry is a candidate only; ESD trigger/current survival is unqualified.',
        'Interconnect resistance/capacitance and mutual coupling require extraction; do not add the full capacitance budget.',
        'Input common mode, power-off loading and clamp stress require the attached core and external network together.',
    ])


FAMILIES=('wired_transmit','reference_clock','rf_receive','rf_transmit','wired_receive_usb')


def build(family='wired_transmit'):
    if family == 'wired_receive_usb':
        from wired_receive import build as build_receive
        return build_receive()
    return wired_transmit() if family=='wired_transmit' else analog_port(family)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--family',choices=FAMILIES,default='wired_transmit')
    args = p.parse_args()
    circuit = build(args.family)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / (circuit.name + '.spice')).write_text(circuit.spice())
    (args.output_dir / (circuit.name + '.json')).write_text(json.dumps(asdict(circuit), indent=2) + '\n')
    print(f'{circuit.name}: {len(circuit.devices)} MOS instances; {len(circuit.ports)} ports')


if __name__ == '__main__':
    main()
