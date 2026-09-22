"""Finite event model of FIFO publication/reuse latency, not analog CDC proof."""
import hashlib
import json
import pathlib
import random


def run(tw, tr, phase, seed, stages=2):
    rng = random.Random(seed)
    w = r = 0
    ws = [0]*stages  # write pointer observed in read domain
    rs = [0]*stages
    mem = [None]*8
    freed = [None]*8
    nw, nr = 0, phase
    reads = reuse = resets = 0
    amin = bmin = float('inf')
    for event in range(6000):
        t = min(nw, nr)
        we, re = nw == t, nr == t
        # Both decisions use pre-edge state, including on coincident edges.
        put = we and w-rs[-1] < 8 and rng.randrange(5) != 0
        take = re and r < ws[-1] and rng.randrange(5) != 0
        ow, ore = w, r
        if take:
            token, written = mem[r % 8]
            assert token == r, 'ordering/storage reuse'
            age = (t-written)/tr
            assert age >= 2, 'publication window'
            amin = min(amin, age)
            freed[r % 8] = t
            r += 1
            reads += 1
        if put:
            idx = w % 8
            if freed[idx] is not None:
                age = (t-freed[idx])/tw
                assert age >= 2, 'reuse window'
                bmin = min(bmin, age)
                reuse += 1
            mem[idx] = (w,t)
            w += 1
        if we:
            # Randomly retain stage 1 to model extra coherent visibility delay.
            rs = [ore if rng.randrange(4) else rs[0]] + rs[:-1]
            nw += tw
        if re:
            ws = [ow if rng.randrange(4) else ws[0]] + ws[:-1]
            nr += tr
        assert 0 <= w-r <= 8
        if event in (1999,3999):
            # Coordinated flush, then conservative blank interval before restart.
            w=r=0;ws=[0]*stages;rs=[0]*stages
            mem=[None]*8;freed=[None]*8
            nw += 3*tw;nr += 3*tr;resets += 1
    assert reads > 100 and reuse > 100
    return dict(reads=reads,reuses=reuse,resets=resets,
                minimum_publication_read_periods=amin,minimum_reuse_write_periods=bmin)


def main():
    cases=[]
    for tw,tr in [(10,10),(10,14),(14,10),(3,31),(31,3),(25,26)]:
        for phase in range(tr):
            for seed in (17,83):
                cases.append(dict(tw=tw,tr=tr,phase=phase,seed=seed,**run(tw,tr,phase,seed)))
    try:
        run(10,14,1,17,stages=1)
    except AssertionError as e:
        assert str(e) in ('publication window','reuse window')
        negative=str(e)
    else:
        raise AssertionError('one-stage negative control escaped')
    root=pathlib.Path(__file__).resolve().parents[1]
    source=pathlib.Path(__file__)
    report=dict(pass_number=60,cases=len(cases),reads=sum(c['reads'] for c in cases),
        reuses=sum(c['reuses'] for c in cases),resets=sum(c['resets'] for c in cases),
        minimum_publication_read_periods=min(c['minimum_publication_read_periods'] for c in cases),
        minimum_reuse_write_periods=min(c['minimum_reuse_write_periods'] for c in cases),
        negative_control=negative,
        scope='Finite abstract event model with coherent delayed pointer observations; not RTL equivalence, metastability, Gray skew, hold or physical signoff.',
        sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,root/'rtl/pt_fifo.sv']})
    (root/'evidence/block-stability-windows.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
