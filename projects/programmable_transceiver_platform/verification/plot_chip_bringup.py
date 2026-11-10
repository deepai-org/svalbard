#!/usr/bin/env python3
"""Render audited bring-up evidence, or an explicitly labeled live diagnostic.

Matplotlib runs in the existing offline analog-tools image. The repository is
mounted read-only and only the experiment's output directory is writable.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
IMAGE = 'docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render(out, live):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
    experiment = json.loads((out/'experiment.json').read_text())
    ui = 1/experiment['data_rate']
    if live:
        raw = json.loads((out/'live-tail-diagnostic.json').read_text())
        note = json.loads((out/'live-preamble-diagnostic.json').read_text())
        t = np.array(raw['time'])
        assert abs(t[-1]-note['time_window_s'][-1]) < 1e-12
        x = (t-experiment['data_start'])*1e9
        fig, axes = plt.subplots(2, 1, figsize=(12, 6), layout='constrained', sharex=True)
        for name, label in [('vdd', 'Ring VDD'), ('xchip.rail_wired', 'Wired rail'), ('xchip.rail_debug', 'Debug rail')]:
            axes[0].plot(x, raw[name], label=label, linewidth=.9)
        axes[0].set(ylabel='Supply (V)', title='Shared supply during the live preamble')
        axes[0].legend(loc='upper right', ncols=3)
        differential = np.array(raw['board_p'])-np.array(raw['board_n'])
        axes[1].plot(x, differential, linewidth=.9)
        for level in (-.25, .25): axes[1].axhline(level, color='#999999', linestyle='--', linewidth=.8)
        axes[1].set(xlabel='Time after input preamble starts (ns)', ylabel='Board differential (V)')
        fig.suptitle('Live preamble diagnostic — milestone pending', fontsize=14)
        fig.supxlabel(f'{note["preamble_bits_checked"]} diagnostic bits, {note["errors"]} errors; fixed delay from independent local training. Final payload is not scored here.', fontsize=9)
        stem = 'live-preamble'
        inputs = ['experiment.json', 'live-tail-diagnostic.json', 'live-preamble-diagnostic.json']
    else:
        report = json.loads((out/'report.json').read_text())
        audit = json.loads((out/'milestone-audit.json').read_text())
        assert report['status'] == audit['status'] == 'pass' and audit['milestone_met']
        assert sha(out/'wave.txt') == audit['waveform_sha256']
        assert sha(out/'report.json') == audit['producer_report_sha256']
        w = np.loadtxt(out/'wave.txt', skiprows=1)
        t = w[:, 0]
        delay = report['data']['trained_delay_s']
        payload = np.array(experiment['payload_bits'])
        sample_t = experiment['data_start']+(experiment['preamble_bits']+
                    len(experiment['training_bits'])+np.arange(len(payload))+.5)*ui+delay
        values = np.interp(sample_t, t, w[:, 27]-w[:, 28])
        margins = values*(2*payload-1)
        assert np.array_equal(values > 0, payload.astype(bool)) and margins.min() >= .25
        fig, axes = plt.subplots(4, 1, figsize=(12, 11), layout='constrained')
        for column, label in [(1, 'Ring VDD'), (4, 'POR_N'), (5, 'Wired rail'), (13, 'Debug rail')]:
            axes[0].plot(t*1e3, w[:, column], label=label, linewidth=.9)
        axes[0].set(xlabel='Time after board power starts (ms)', ylabel='Voltage (V)', title='Cold power-up')
        axes[0].legend(ncols=4, loc='upper left')
        zoom = t >= .04999
        for column, label in [(5, 'Wired rail'), (13, 'Debug rail'), (3, 'DBG_OBS0')]:
            axes[1].plot((t[zoom]-.05)*1e6, w[zoom, column], label=label, linewidth=.9)
        for read in report['spi_reads']:
            timing = next(r for r in experiment['reads'] if r['address'] == read['address'] and r['expected'] == read['expected'])
            when = (np.mean(timing['sample_times'])-.05)*1e6
            axes[1].annotate(f'{read["address"]:02X}:{read["actual"]:04X}', (when, 3.35), fontsize=8, ha='center')
        axes[1].set(xlabel='Time after SPI starts (µs)', ylabel='Voltage (V)', ylim=(-.15, 3.65), title='SPI-controlled islands and observation')
        axes[1].legend(ncols=3, loc='lower right')
        start, end = experiment['data_start'], experiment['data_end']
        data = (t >= start-10e-9)&(t <= end+15e-9)
        axes[2].plot((t[data]-start)*1e9, (w[data, 27]-w[data, 28]), linewidth=.8, label='Board differential')
        axes[2].scatter((sample_t-start)*1e9, values, color='#167d3d', s=10, label='Payload samples')
        boundary = experiment['preamble_bits']*ui+delay
        axes[2].axvspan(boundary*1e9, (boundary+len(experiment['training_bits'])*ui)*1e9, color='#87b8df', alpha=.2, label='Distinct training word')
        for level in (-.25, .25): axes[2].axhline(level, color='#999999', linestyle='--', linewidth=.8)
        axes[2].set(xlabel='Time after input preamble starts (ns)', ylabel='Differential (V)', title=f'{len(payload)} payload bits at {experiment["data_rate"]/1e6:g} Mb/s; zero errors')
        axes[2].legend(ncols=3, loc='lower left')
        axes[3].plot(np.arange(len(payload)), margins*1e3, '.-', color='#167d3d', linewidth=.8)
        axes[3].axhline(250, color='#b35900', linestyle='--', label='250 mV required')
        axes[3].set(xlabel='Payload bit', ylabel='Signed sample margin (mV)',
                    title=f'Minimum payload margin {margins.min()*1e3:.1f} mV; phase learned only from training')
        axes[3].legend(loc='lower right')
        fig.suptitle('Audited nominal assembled bring-up', fontsize=14)
        fig.supxlabel('RTL plus extracted analog, with schematic control glue in this cold-start run. Full-chip physical, PVT and BER signoff remain outside this result.', fontsize=9)
        stem = 'bringup-evidence'
        inputs = ['experiment.json', 'report.json', 'milestone-audit.json', 'wave.txt']
    for axis in axes: axis.grid(alpha=.2)
    fig.savefig(out/(stem+'.png'), dpi=150)
    fig.savefig(out/(stem+'.svg'))
    plt.close(fig)
    metadata = dict(scope='live_diagnostic_only' if live else 'audited_nominal_milestone',
                    source_artifacts={name: sha(out/name) for name in inputs},
                    plotter_sha256=sha(__file__), image=IMAGE,
                    outputs={suffix: sha(out/(stem+suffix)) for suffix in ('.png', '.svg')})
    (out/(stem+'-plot.json')).write_text(json.dumps(metadata, indent=2)+'\n')
    print('Rendered '+stem)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/chip-fallback-burst')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--inside-container', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside_container:
        render(args.output_dir, args.live)
    else:
        command = 'python3 /repo/projects/programmable_transceiver_platform/verification/plot_chip_bringup.py --inside-container --output-dir /work'
        if args.live: command += ' --live'
        result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '4g',
            '--entrypoint', '/bin/bash', '-e', 'MPLBACKEND=Agg', '-v', f'{ROOT}:/repo:ro',
            '-v', f'{args.output_dir.resolve()}:/work', '-w', '/work', IMAGE, '-lc', command], capture_output=True, text=True)
        (args.output_dir/'plot.log').write_text(result.stdout+result.stderr)
        result.check_returncode()
        print('Plots written in '+str(args.output_dir.resolve()))
