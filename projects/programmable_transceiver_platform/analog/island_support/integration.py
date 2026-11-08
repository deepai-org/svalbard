"""Integration fixture: an off RF island back-driven from its RF_TX pad, with
iso_clamp cells at the core boundary in both directions.

Netlist (extracted C-coupled RF switch and iso_clamp when available):
  RF_TX pad -> diode + 28 ohm (driver output junctions, ~90 mA into a 0 V rail)
            -> VISL (RF island rail, 200 pF, optional RF-allocation load)
  island output stage: inverter on VISL, input low  -> drives ISL_OUT = VISL (worst case)
  core <- island: iso_clamp(A=ISL_OUT, ISO) -> CORE_IN -> core inverter load
  core -> island: iso_clamp(A=VDD (mis-programmed high), ISO) -> ISL_IN
                  -> island input gate + ESD diode to VISL
EN = 0 (island off). Checks: CORE_IN and ISL_IN stay low, current into the
ring stays at leakage, ISO stays high when the ring is powered.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design  # noqa: E402
import sim  # noqa: E402

ISW_PORTS = ['VDD', 'VSS', 'VISL', 'EN', 'ISO', 'PG']
CLAMP_PORTS = ['A', 'ISO', 'Y', 'VDD', 'VSS']


def fixture(nf, corner, temp, vdd, pad, load, tran=False, en='0', en_tag='off'):
    t = sim.header(corner, temp)
    t += sim.OVERRIDE.get('isw') or design.isw_netlist('isw', nf)
    t += sim.OVERRIDE.get('iso_clamp') or design.iso_clamp_netlist('iso_clamp')
    t += '.model DJ D(IS=1e-14 N=1)\n.model DESD D(IS=1e-16 N=1)\n'
    if tran:
        t += f'VDD VDD 0 PWL(0 0 2u {vdd})\nVPAD PAD 0 PWL(0 0 10u 0 10.1u {pad})\n'
    else:
        t += f'VDD VDD 0 {vdd}\nVPAD PAD 0 {pad}\n'
    t += (f'VEN EN 0 {en}\nDJ PAD PJ DJ\nRJ PJ VISL 28\nCI VISL 0 200p\n'
          + (f'RL VISL 0 {load}\n' if load else '') +
          'XI VDD 0 VISL EN ISO PG isw\n'
          # island output stage (input held low -> output follows VISL)
          'XOP ISL_OUT 0 VISL VISL pfet_03v3 w=2u l=0.28u\nXON ISL_OUT 0 0 0 nfet_03v3 w=1u l=0.28u\n'
          'XC1 ISL_OUT ISO CORE_IN VDD 0 iso_clamp\n'
          'XLP CL CORE_IN VDD VDD pfet_03v3 w=1u l=0.28u\nXLN CL CORE_IN 0 0 nfet_03v3 w=0.5u l=0.28u\n'
          'XC2 VDD ISO ISL_IN VDD 0 iso_clamp\n'
          'XIP IG ISL_IN VISL VISL pfet_03v3 w=1u l=0.28u\nXIN IG ISL_IN 0 0 nfet_03v3 w=0.5u l=0.28u\n'
          'DESD ISL_IN VISL DESD\n')
    if tran:
        t += ('.tran 10n 40u\n.control\nrun\n'
              'meas tran core_in_max max v(core_in) from=2.5u to=40u\n'
              'meas tran isl_in_max max v(isl_in) from=2.5u to=40u\n'
              'meas tran i_ring_max max i(vdd) from=2.5u to=40u\n'
              'meas tran q_ring_hotplug integ i(vdd) from=10u to=12u\n'
              'meas tran visl_end find v(visl) at=39u\nmeas tran iso_min min v(iso) from=2.5u to=40u\n'
              'meas tran core_in_end find v(core_in) at=39u\n.endc\n.end\n')
    else:
        t += ('.control\nop\nlet core_in = v(core_in)\nprint core_in\nlet isl_in = v(isl_in)\nprint isl_in\n'
              'let i_into_ring = i(vdd)\nprint i_into_ring\nlet visl_v = v(visl)\nprint visl_v\n'
              'let iso_v = v(iso)\nprint iso_v\nlet pg_v = v(pg)\nprint pg_v\nlet i_pad = -i(vpad)\nprint i_pad\n'
              'let i_esd = @desd[id]\nprint i_esd\n.endc\n.end\n')
    tag = 'tran' if tran else 'op'
    return (f'int_{tag}_{corner}_{temp}_{vdd}_{pad}_{load}_{en_tag}', t)


def main():
    work = Path('/work')
    S = json.loads((work / 'schematic-result.json').read_text())
    workers = int(os.environ.get('WORKERS', os.cpu_count() or 2))
    nf = S['sizes']['rf']['fingers']
    rl = round(3.3 / (S['allocation']['rf']['peak_allocation_ma'] * 1e-3), 1)
    out = {}
    for label, use_pex in (('schematic', False), ('extracted', True)):
        sim.OVERRIDE.clear()
        sim.WORK = work / f'sims_int_{label}'
        if use_pex:
            for cell, name, ports in (('isw_rf', 'isw', ISW_PORTS), ('iso_clamp', 'iso_clamp', CLAMP_PORTS)):
                p = work / ('pex' if cell.startswith('isw') else 'pexd') / cell / f'{cell}.pex.spice'
                if not p.exists():
                    out[label] = {'error': f'missing {p}'}
                    break
                sim.OVERRIDE[name] = sim.load_pex(p, name, ports)
            else:
                pass
            if 'error' in out.get(label, {}):
                continue
        jobs = [fixture(nf, c, tc, vdd, pad, ld) for c in ('tt', 'ss', 'ff') for tc in (0, 27, 85)
                for vdd in (0.0, 3.3) for pad in (3.3, 3.63) for ld in (None, rl)]
        jobs += [fixture(nf, c, 27, 3.3, 3.63, None, tran=True) for c in ('tt', 'ss', 'ff')]
        # Transparency sanity: island on, no back-drive -> CORE_IN follows the island output (high).
        jobs += [fixture(nf, c, 27, 3.3, 0.0, rl, tran=True, en='PWL(0 0 20u 0 20.01u 3.3)', en_tag='on') for c in ('tt', 'ss', 'ff')]
        res = sim.run_all(jobs, workers)
        op = {k: {kk: v for kk, v in r.items() if not kk.startswith('_')} for k, r in res.items() if k.startswith('int_op')}
        tr = {k: {kk: v for kk, v in r.items() if not kk.startswith('_')} for k, r in res.items() if k.startswith('int_tran')}
        bd = {k: v for k, v in tr.items() if k.endswith('_off')}
        on = {k: v for k, v in tr.items() if k.endswith('_on')}
        powered = [v for k, v in op.items() if k.split('_')[4] == '3.3']
        out[label] = {
            'op_cases': len(op),
            'core_in_max_v': max(v['core_in'] for v in op.values()),
            'isl_in_max_v': max(v['isl_in'] for v in op.values()),
            'i_into_ring_max_a': max(v['i_into_ring'] for v in op.values()),
            'i_esd_island_input_max_a': max(v['i_esd'] for v in op.values()),
            'visl_range_v': [min(v['visl_v'] for v in op.values()), max(v['visl_v'] for v in op.values())],
            'i_pad_max_a': max(v['i_pad'] for v in op.values()),
            'iso_high_ring_powered': all(v['iso_v'] > 3.0 for v in powered),
            'hotplug_core_in_max_v': max((v.get('core_in_max', 9) for v in bd.values()), default=None),
            'hotplug_isl_in_max_v': max((v.get('isl_in_max', 9) for v in bd.values()), default=None),
            'hotplug_i_ring_max_a': max((v.get('i_ring_max', 9) for v in bd.values()), default=None),
            'island_on_core_in_end_v': [v.get('core_in_end') for v in on.values()],
            'cases': {**op, **tr},
        }
        out[label]['hotplug_note'] = ('hotplug_i_ring_max_a is the capacitive displacement current of the 0->3.63 V/100 ns pad '
                                      'step through the off pass device, not DC conduction; q_ring_hotplug in the tran cases '
                                      'is its integrated charge into the ring.')
        ok = (out[label]['core_in_max_v'] < 0.3 and out[label]['isl_in_max_v'] < 0.3
              and out[label]['i_into_ring_max_a'] < 10e-6 and out[label]['iso_high_ring_powered']
              and out[label]['hotplug_core_in_max_v'] < 1.0 and out[label]['hotplug_isl_in_max_v'] < 1.0
              and all(x is not None and x > 3.0 for x in out[label]['island_on_core_in_end_v']))
        out[label]['verdict'] = 'pass' if ok else 'fail'
    (work / 'integration-result.json').write_text(json.dumps(out, indent=1))
    print('wrote /work/integration-result.json')


if __name__ == '__main__':
    main()
