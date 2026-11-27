#!/usr/bin/env python3
"""pin_order_plan.py <chip> <ref.lef> <out.cfg>: flow pin order for the floorplan-plan pin sides
(integration/assembly/fp_plan/<chip>_macro_pin_order.cfg, coordinator option A 2026-11-26).

* Pins listed in the plan go to the planned side at the slot nearest the planned offset.
* The host-link group (h2d_*, d2h_*, host_word_clk) stays one cluster at its current position (taken from <ref.lef>,
  the delivered macro): its capture / launch flops are hand-placed under it (hio_shift.py).
* Pins the plan leaves out (tie-offs and others) stay where they are in <ref.lef>.
Every side is written slot by slot: slot i at 0.28 + 2.24 * i um, padded with virtual pins ($n) to one less than the
slot count, so io_place.py puts entry i at slot i (same scheme as pin_order_wired.py). Fixed pins (host link, kept)
take their slots first; planned pins then take the free slot nearest their target, in plan order.
"""
import re, sys
from pathlib import Path

H = Path(__file__).resolve().parent
PLAN = H.parents[1] / 'integration/assembly/fp_plan'
HOST = re.compile(r'^(h2d_|d2h_|host_word_clk$)')
X0, PITCH = 0.28, 2.24


def lef_pins(lef):
    t = Path(lef).read_text()
    W, Hh = map(float, re.search(r'SIZE ([\d.]+) BY ([\d.]+)', t).groups())
    pins = {}
    for m in re.finditer(r'PIN (\S+)\n(.*?)END \1\n', t, re.S):
        n = m.group(1)
        if n in ('VDD', 'VSS'):
            continue
        r = re.search(r'RECT ([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+)', m.group(2))
        x1, y1, x2, y2 = map(float, r.groups())
        x, y = (x1 + x2) / 2, (y1 + y2) / 2
        side = 'S' if y < 3 else 'N' if y > Hh - 3 else 'W' if x < 3 else 'E'
        pins[n] = (side, x if side in 'NS' else y)
    return W, Hh, pins


def plan_pins(chip):
    out, side = [], None
    for l in (PLAN / f'{chip}_macro_pin_order.cfg').read_text().splitlines():
        t = l.split()
        if len(t) == 1 and re.fullmatch(r'#[NSEW]', t[0]):
            side = t[0][1]
            continue
        if not t or l.startswith('#'):
            continue
        out.append((t[0], side, float(t[1])))
    return out


def main():
    chip, ref, dst = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    W, Hh, cur = lef_pins(ref)
    # slot count = every 4th Metal2 / Metal3 track; track counts as OpenROAD reports them (io_place.py log, origin 0.28 um,
    # step 0.56 um): they do not follow one rounding rule, so they are listed per outline
    tracks = {(1716.0, 1365.6): (3064, 2438), (1676.0, 1592.96): (2993, 2844)}[(W, Hh)]
    nslot = {s: len(range(0, tracks[0] if s in 'NS' else tracks[1], 4)) for s in 'NSEW'}
    slots = {s: {} for s in 'NSEW'}
    slot = lambda v: round((v - X0) / PITCH)

    def take(side, target, name):
        s0 = max(0, min(nslot[side] - 2, slot(target)))
        for d in range(nslot[side]):
            for s in (s0 + d, s0 - d):
                if 0 <= s < nslot[side] - 1 and s not in slots[side]:
                    slots[side][s] = name
                    return
        sys.exit(f'{side}: no free slot for {name}')

    planned = [p for p in plan_pins(chip) if not HOST.match(p[0])]
    missing = [p[0] for p in planned if p[0] not in cur]
    assert not missing, f'plan pins not on the macro: {missing[:5]}'
    pset = {p[0] for p in planned}
    fixed = sorted((n for n in cur if n not in pset), key=lambda n: (not HOST.match(n), cur[n][1]))
    for n in fixed:                      # host-link group first, then the kept pins, at today's positions
        take(cur[n][0], cur[n][1], n)
    for n, side, off in planned:
        take(side, off, n)
    assert sum(len(v) for v in slots.values()) == len(cur)
    lines = []
    for side in 'SNWE':
        lines += [f'#{side}', f'@min_distance={PITCH}']
        last = 0
        for s in sorted(slots[side]):
            if s > last:
                lines.append(f'${s - last}')
            lines.append(re.escape(slots[side][s]).replace('\\_', '_'))
            last = s + 1
        if nslot[side] - 1 > last:
            lines.append(f'${nslot[side] - 1 - last}')
    dst.write_text('\n'.join(lines) + '\n')
    host_moved = [n for n in cur if HOST.match(n) and abs(X0 + PITCH * next(s for s, v in slots[cur[n][0]].items() if v == n) - cur[n][1]) > 1.2]
    print(chip, {s: len(slots[s]) for s in 'NSEW'}, 'slots', nslot, 'planned', len(planned), 'kept', len(fixed),
          'host-link pins moved > 1.2 um:', host_moved)


if __name__ == '__main__':
    main()
