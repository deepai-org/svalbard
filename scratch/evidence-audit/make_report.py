#!/usr/bin/env python3
"""Evidence audit: assemble the per-block table from the result files (inventory.json, freshness.json,
drc-results*.jsonl, lvs-results*.jsonl, sch-results.jsonl, bench_notes.py). Prints markdown rows; the prose
of scratch/reviews/evidence-audit.md is hand-written around it.   Usage: python3 make_report.py > table.md"""
import json, sys, pathlib, re
H = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from bench_notes import BENCH
inv = json.loads((H / 'inventory.json').read_text())['blocks']
fresh = json.loads((H / 'freshness.json').read_text())
def jl(p):
    out = {}
    if (H / p).exists():
        for l in (H / p).read_text().splitlines():
            try: r = json.loads(l); out[r.get('name') or r.get('block')] = r
            except Exception: pass
    return out
drc = jl('drc-results.jsonl'); drc.update(jl('drc-results2.jsonl')) if False else None
drc2 = jl('drc-results.jsonl')
lvs = jl('lvs-results.jsonl'); lvx = jl('lvs-results-extra.jsonl'); sch = jl('sch-results.jsonl')

# schematic generator at HEAD reproduces the committed <block>.spice (run in an export of HEAD, see section 2)
REPRO = {}
for n in 'lna rxmix_i rxmix_q bb_tap txmix_i txmix_q txsum rfdriver adc_i adc_q dac_i dac_q refbuf cdr ctle detect rxlevel rxselect slicer termination wmon_sel pt_ptrim pt_vthdac wiredtx hsbias pt_usb_txdrv char_atb char_ro33 char_ro50 char_cmldiv pt_bias_tap2 pt_refvcm pt_txpad_bias'.split(): REPRO[n] = 'yes'
REPRO.update(bbfilter_i='NO', bbfilter_q='NO')
for n in 'pll_ring pt_pll_ring_core clockmux prescale wordclk lo_ext clk_obs pt_clk_obs16 pt_obs_pre4 diff_clk_rx ring_osc vco_replica aosc pt_lo_mmd pt_lo_mmd_qdum pt_lo_pfdcp pt_lo_lf pt_lo_obs pt_lc_qvco5'.split(): REPRO[n] = 'source'
ORDER = [('RF receive', 'lna rxmix_i rxmix_q bbfilter_i bbfilter_q bb_tap'), ('RF transmit', 'txmix_i txmix_q txsum rfdriver'),
         ('Converters', 'adc_i adc_q dac_i dac_q refbuf'),
         ('LO, clocks, PLLs', 'pt_lc_qvco5 pt_lo_mmd pt_lo_mmd_qdum pt_lo_pfdcp pt_lo_lf pt_lo_obs lo_ext pll_ring pt_pll_ring_core pt_pll_vreg2 clockmux prescale wordclk diff_clk_rx pt_clk_obs16 pt_obs_pre4 ring_osc vco_replica aosc clk_obs'),
         ('Wired receive', 'cdr ctle detect rxlevel rxselect slicer termination wmon_sel pt_ptrim pt_vthdac pt_wrx_cap'),
         ('Wired transmit and USB', 'wiredtx pt_usb_txdrv hsbias wtx_fallback_control tx_steering_buffer_flat buffer_compensated_flat attached_tx_interlock'),
         ('Pads', 'pad_rf_pair pad_rftxpad pad_single_leg pad_refpad pad_hspad pad_wirepad pad_txpad pad_tlp'),
         ('Core, bias, islands, test bus', 'por pt_core_bias pt_bias_tap2 pt_refvcm pt_txpad_bias isw_wired isw_rf isw_conv isw_debug iso_clamp atb_leaf_s atb_leaf_f atb_grp atb_pad'),
         ('Characterization and decap', 'char_atb char_ro33 char_ro50 char_cmldiv char_rffet char_rffet_open char_rffet_short pt_decap_tile'),
         ('Published GDS that the chip top does not bind', 'isw_pll pt_pll_vreg attached_tx_steering_driver attached_tx_buffer')]
BIND = {'tx_steering_buffer_flat': 'tx_steer (published)', 'buffer_compensated_flat': 'term_buffer (published)', 'attached_tx_interlock': 'tx_interlock (published)',
        'pt_core_bias': 'pt_core_bias (inline pin list)', 'pt_bias_tap2': 'not bound', 'pt_refvcm': 'demand in masters.txt', 'pt_txpad_bias': 'demand in masters.txt',
        'clk_obs': 'not bound', 'isw_pll': 'not bound', 'pt_pll_vreg': 'not bound', 'attached_tx_steering_driver': 'not bound', 'attached_tx_buffer': 'not bound', 'pt_decap_tile': 'not in the conn'}
# manual verdict inputs: pass states that the record's own numbers contradict / evidence of another cell / chip binds another contract
CONTRA = {'lna': 'pass states against failing own numbers', 'rxmix_i': 'pass states against failing rows', 'rxmix_q': 'pass states against failing rows',
          'detect': 'clean = pass with two gating corner failures recorded', 'adc_q': 'pass from one run; all_pass over an empty corner set',
          'pll_ring': 'observable = pass with the lock flag wrong in 3 of 5 runs', 'vco_replica': 'clean = pass with 12 of 48 corner cases failing'}
OTHERCELL = {'pt_lc_qvco5': 'the only record (lcvco-evidence.json) is of the previous cell, schematic level', 'lo_ext': 'record is of the superseded layout',
             'hsbias': 'record hashes another netlist'}
STAGED = {'adc_i', 'adc_q', 'dac_i', 'dac_q'}
KNOWN_BAD = {'pad_hspad': 'published cell cannot be trimmed to 100 ohm when metal resistance is extracted (owner result, fix staged)',
             'wiredtx': 'fails 2.5 Gb/s at ss on the real ring'}
NO_SIM_OK = {'char_rffet', 'char_rffet_open', 'char_rffet_short', 'pad_tlp'}   # probe / measurement structures

def drc_cell(n):
    names = {'pad_rf_pair': 'pad_rf_pair__top_pad_rf_pair', 'pt_core_bias': 'pt_core_bias'}
    r = drc2.get(names.get(n, n)) or drc2.get(n)
    rec = inv.get(n, {}).get('kldrc')
    if n == 'pt_core_bias': rec = None
    if not r: return '?', 'not run'
    if r.get('clean'): s = '0 / 0'
    elif r.get('error') or any(v.get('total') is None for v in r.get('decks', {}).values()): s = 'run error'
    else:
        s = ' / '.join(str(v.get('total')) for v in r['decks'].values())
        rules = [f'{k} x{c}' for v in r['decks'].values() for k, c in (v.get('rules') or {}).items()]
        s = '**' + s + '** (' + ', '.join(rules[:2]) + ')'
    s += '' if (rec or n == 'pt_usb_txdrv') else '; no record'      # usbdrv-kldrc.json matches the GDS (block is not in inventory.json)
    return ('ok' if r.get('clean') else 'fail'), s

def lvs_cell(n):
    r = lvs.get(n); s = sch.get(n, {}); parts = []; ok = True
    if n == 'pt_core_bias':
        leaves = [v for k, v in lvx.items() if k.startswith('core_bias__')]
        good = sum(1 for v in leaves if v.get('status') == 'match')
        return ('ok' if leaves and good == len(leaves) else 'part'), f'leaf by leaf: {good}/{len(leaves)} leaves match; no flat netlist for the assembly'
    if n == 'attached_tx_interlock':
        r = lvx.get('bound__tx_interlock')
        if not r: return 'part', 'not run'
    if not r: return 'part', 'not run'
    if r.get('status') == 'match' or (n in ('tx_steering_buffer_flat', 'buffer_compensated_flat') and r.get('netgen_unique')): parts.append('bound netlist: match')
    elif n in ('char_rffet_open', 'char_rffet_short') and r.get('census_match'): parts.append('no devices on either side')
    elif 'nowell' in s and s['nowell'].get('census_equal'):
        parts.append('bound netlist: devices and nets equal after removing its one modelled well diode; layout pin ESD_RAIL is not in the bound subcircuit')
    elif n == 'attached_tx_interlock' and r.get('netgen_unique'): parts.append('bound netlist: match')
    else:
        ok = False; parts.append('bound netlist: **' + ((r.get('what') or r.get('why') or 'mismatch').replace('netgen: Final result: ', '').split('\n')[0][:70]) + '**')
    h = s.get('head')
    if h:
        d = h.get('antenna_diodes_layout') or 0
        if h.get('unique'): parts.append('committed schematic: match' + (f' (+{int(d)} antenna diodes)' if d else ''))
        else:
            ok = False
            wt = s.get('worktree', {}).get('unique')
            parts.append('committed schematic: **no match**' + (' (matches the uncommitted one)' if wt else ''))
    bx = {'tx_steering_buffer_flat': 'bound__tx_steer', 'buffer_compensated_flat': 'bound__term_buffer'}.get(n)
    if bx and lvx.get(bx):
        parts.append('chip-top netlist (lifecycle file): ' + ('match' if lvx[bx].get('netgen_unique') else '**no match**')); ok = ok and bool(lvx[bx].get('netgen_unique'))
    if n == 'pt_lc_qvco5':
        parts = ['core subcell: ' + ('match' if r.get('status') == 'match' else 'mismatch') +
                 '; top cell against qvco5.spice: **cannot match** (the two spirals extract as metal shorts between IP/IN and QP/QN), spiral hookup unverified']
        return 'part', parts[0]
    return ('ok' if ok else 'fail'), '; '.join(parts)

ALT = {  # record used where the family has no <block>-evidence.json (hash state read today)
 'pad_rf_pair': 'pad-layout.json + pd13-family-sims.json: GDS and extracted-netlist hashes match', 'pad_rftxpad': 'pd48-esd-tiering.json: hashes match',
 'pad_single_leg': 'layout record only: hashes match', 'pad_refpad': 'pd13-family-sims.json: model hash matches; sims script changed since',
 'pad_hspad': 'ap4-hspad-*.json: model hash matches; layout-screen.json records a generator that has uncommitted edits',
 'pad_wirepad': 'pd47-usb-ls-miller.json, pd48-esd-tiering.json: model hash matches', 'pad_txpad': 'pd13-family-sims.json: model hash matches; generator committed after the build',
 'pad_tlp': 'kldrc record only; the review covers another GDS hash', 'por': 'core_support_evidence.json: all 34 source hashes match',
 'pt_bias_tap2': 'layout.json: GDS and netlist hashes match', 'pt_refvcm': 'layout.json: GDS and netlist hashes match', 'pt_txpad_bias': 'layout.json: GDS and netlist hashes match; sims hash another build',
 'isw_wired': 'island_support/evidence.json: GDS and netlist hashes match (files under scratch/); design.py, layout.py changed since', 'isw_rf': 'as isw_wired', 'isw_conv': 'as isw_wired', 'isw_debug': 'as isw_wired', 'isw_pll': 'as isw_wired',
 'iso_clamp': 'island_support/evidence.json: hashes match (scratch/)', 'atb_leaf_s': 'island_support/evidence.json hashes the pex/ netlists; the bound pexd/ netlist is in no record', 'atb_leaf_f': 'as atb_leaf_s', 'atb_grp': 'as atb_leaf_s', 'atb_pad': 'as atb_leaf_s',
 'char_ro33': 'char_speed-evidence.json section + physical.json', 'char_ro50': 'as char_ro33', 'char_cmldiv': 'as char_ro33',
 'char_rffet': 'physical.json only; GDS rebuilt 18 Nov', 'char_rffet_open': 'as char_rffet', 'char_rffet_short': 'as char_rffet',
 'pt_usb_txdrv': 'usbdrv-evidence.json: input hashes match; no tests section', 'pt_pll_vreg2': 'evidence/pd28-*.json: netlist hash matches; ring netlist in the runs has changed since', 'pt_pll_vreg': 'evidence/pll_vreg-ext-packed.json',
 'pt_decap_tile': 'generated/sim-results.json (no evidence JSON)', 'wtx_fallback_control': 'generated/characterization.json (no evidence JSON)',
 'tx_steering_buffer_flat': 'layout.json + equivalence.json: netlist hash matches', 'buffer_compensated_flat': 'readiness-settle.json: no hash of what it simulated',
 'hsbias': 'usb_hs_bias-evidence.json hashes a 10 Nov wiredtx state, not this cell'}
fresh2 = json.loads((H / 'freshness2.json').read_text())
LAYF = re.compile(r'\.(mag|ext\.spice|lvs\.spice)$')
def fresh_cell(n):
    f = fresh.get(n, {}); f2 = fresh2.get(n)
    if not f2:
        return ('alt' if n in ALT else 'none'), ALT.get(n, '**no evidence record**')
    d = (f.get('evidence_commit') or ['?'])[0][5:10]
    def judge(rows):
        lay = [x['file'] for x in rows if LAYF.search(x['file']) and x['disk'] is not True]
        own = [x for x in rows if x['file'].endswith('.spice') and not LAYF.search(x['file']) and x['disk'] is not True]
        gds = [x['file'] for x in rows if x['file'].endswith('.gds') and x['disk'] is not True]
        scr = [x['file'] for x in rows if x['file'].endswith(('.py', '.sh')) and x['disk'] is not True]
        has = [x for x in rows if LAYF.search(x['file']) or x['file'].endswith('.gds')]
        if lay or any(x.get('head') is False for x in own):
            return 'stale', 'recorded ' + ', '.join((lay + [x['file'] for x in own])[:3]) + (' differ' if len(lay + own) > 1 else ' differs') + ' from what is on disk'
        t = []
        if own: t.append('record matches the committed netlist; the netlist has uncommitted edits')
        if gds: t.append('netlist hashes match; GDS hash differs (re-exported after the record)')
        if not own and not gds: t.append('recorded hashes match' if has else 'source hashes match; no layout or GDS hash recorded')
        if scr: t.append(f'{len(scr)} flow or bench scripts changed since')
        return ('ok' if not own and not gds else 'minor'), '; '.join(t)
    k, t = judge(f2['worktree'])
    if f2.get('dirty') and 'committed' in f2:
        kc, tc = judge(f2['committed'])
        t = f'committed record ({d}): ' + tc + '. Uncommitted record: ' + t
        k = kc
    else:
        t = f'{d}: ' + t
    if k == 'stale': t = '**stale** ' + t
    if not f2['worktree']: k, t = 'nohash', f'{d}: record carries no file hashes'
    return k, t

rows = []; fails = []
for title, names in ORDER:
    rows.append(f'\n**{title}**\n')
    rows.append('| Block | Chip-top binding | Netlist reproduces | DRC main / antenna | LVS on the GDS read back | Evidence freshness | Bench realism | Verdict |')
    rows.append('|---|---|---|---|---|---|---|---|')
    for n in names.split():
        b = inv.get(n, {})
        bind = BIND.get(n) or (b.get('master', '') + (' (' + b.get('master_kind', '') + ')' if b.get('master_kind') else '')) or 'not bound'
        dk, ds = drc_cell(n); lk, ls = lvs_cell(n); fk, fs = fresh_cell(n)
        bench, prob = BENCH.get(n, ('?', '?'))
        why = []
        if dk == 'fail': why.append('DRC fails')
        if lk == 'part' and n == 'pt_lc_qvco5': why.append('top cell has no passing LVS')
        if lk == 'fail': why.append('LVS: GDS does not match ' + ('the committed schematic' if 'committed schematic: **no match**' in ls else 'its netlist'))
        if REPRO.get(n) == 'NO': why.append('committed generator does not reproduce the committed netlist')
        tests = fresh.get(n, {}).get('tests') or {}
        if fk == 'none' and n not in NO_SIM_OK:
            why.append('no evidence record')
        if fk == 'stale': why.append('evidence is of another layout or netlist')
        for t in ('safe', 'clean'):
            if str(tests.get(t, '')).startswith('fail'): why.append(f'record says {t} = fail')
        if n in CONTRA: why.append(CONTRA[n])
        if n in OTHERCELL: why.append(OTHERCELL[n])
        if n in STAGED: why.append('chip top binds a newer (staged) pin contract than this cell')
        if n in KNOWN_BAD: why.append(KNOWN_BAD[n])
        if n in ('pt_core_bias',): why.append('no evidence for the assembly; GDS only in scratch')
        if n in ('attached_tx_interlock',): why.append('no evidence for this GDS')
        if title.startswith('Published GDS that'): verdict = 'not used on the chip'
        elif why: verdict = '**not supported**'; fails.append((n, b.get('top', n), why))
        else: verdict = 'physical checks hold, evidence partial'
        rep = REPRO.get(n, 'not checked')
        rep = {'source': 'hand-written source', 'NO': '**no**'}.get(rep, rep)
        rows.append(f'| `{n}` | {bind} | {rep} | {ds} | {ls} | {fs} | {bench} | {verdict}. {prob[0].upper() + prob[1:]} |')
print('\n'.join(rows))
print('\n\n## FAILS\n')
for n, top, why in fails: print(f'- `{n}`: ' + '; '.join(dict.fromkeys(why)) + '.')
print(len(fails), file=sys.stderr)
