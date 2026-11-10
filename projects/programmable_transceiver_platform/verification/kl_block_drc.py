#!/usr/bin/env python3
"""Per-block KLayout DRC + antenna runner (the tapeout precheck's decks, run on one block GDS).

Mirrors the precheck invocation (gf180mcu.drc, variant D, deep mode):
  main    : decks = all,-antenna,-density,-cup
  antenna : decks = antenna
Density is a full-chip rule and CUP is disabled in the precheck, so neither applies to a block.
KLayout 0.30.9 from the pinned iic-osic-tools image (0.30.7 in the precheck image crashes on antenna).

  kl_block_drc.py --block NAME                     (GDS/top from kl_block_drc_blocks.json)
  kl_block_drc.py --gds X.gds[.gz] --top CELL --name NAME [--out DIR] [--threads N] [--decks main,antenna]
  --publish   also write <gds dir>/<name>-kldrc.json (the block-evidence record that
              check_block_kldrc.py requires: clean, and gds_sha256 equal to the current GDS)

Writes <out>/<name>/{main,antenna}.lyrdb, logs and <out>/<name>/kldrc.json:
  {block, gds, gds_sha256, top, klayout, decks:{main:{total,rules}, antenna:{...}}, clean}
Exit status 0 only when every requested deck reports zero items.
"""
import argparse, collections, gzip, hashlib, json, os, pathlib, shutil, subprocess, sys
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parent
REPO = PROJECT.parents[1]
IMAGE = "sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305"
DECKS = {"main": "all,-antenna,-density,-cup", "antenna": "antenna"}
REGISTRY = HERE / "kl_block_drc_blocks.json"
DEFAULT_OUT = REPO / "scratch" / "kl-block-drc"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_lyrdb(path):
    by_rule, by_cell = collections.Counter(), collections.defaultdict(collections.Counter)
    for _, el in ET.iterparse(path, events=("end",)):
        if el.tag == "item":
            r = (el.findtext("category") or "?").strip("'")
            by_rule[r] += 1
            by_cell[el.findtext("cell") or "?"][r] += 1
            el.clear()
    return dict(total=sum(by_rule.values()), rules=dict(by_rule.most_common()),
                cells={c: dict(v.most_common()) for c, v in by_cell.items()})


def resolve(entry):
    p = pathlib.Path(entry)
    return p if p.is_absolute() else REPO / p


def publish(res):
    """Compact evidence record next to the block GDS."""
    rec = {k: res[k] for k in ('block', 'gds_sha256', 'top', 'klayout', 'image', 'variant', 'run_mode', 'clean')}
    rec['gds'] = pathlib.Path(res['gds']).name
    rec['deck'] = 'gf180mcu.drc (precheck decks: ' + '; '.join(f'{k}={DECKS[k]}' for k in res['decks']) + ')'
    rec['decks'] = {k: dict(total=v.get('total'), rules=v.get('rules'), error=v.get('error'))
                    for k, v in res['decks'].items()}
    path = pathlib.Path(res['gds']).parent / f"{res['block']}-kldrc.json"
    path.write_text(json.dumps(rec, indent=1) + '\n')
    return path


def run(name, gds, top, out=DEFAULT_OUT, threads=4, decks=("main", "antenna"), do_publish=False):
    """Run the precheck decks on one block GDS; returns the result dict (see module doc)."""
    out = pathlib.Path(out)
    gds = pathlib.Path(gds)
    work = out / name
    work.mkdir(parents=True, exist_ok=True)
    local = work / "in.gds"
    if str(gds).endswith(".gz"):
        with gzip.open(gds, "rb") as fi, open(local, "wb") as fo:
            shutil.copyfileobj(fi, fo)
    else:
        shutil.copyfile(gds, local)
    res = dict(block=name, gds=str(gds), gds_sha256=sha256(gds), top=top, image=IMAGE,
               variant="D", run_mode="deep", decks={})
    for deck in decks:
        rep = f"/work/{deck}.lyrdb"
        (work / f"{deck}.lyrdb").unlink(missing_ok=True)
        cmd = ("export PDK=gf180mcuD PDK_ROOT=/foss/pdks "
               "KLAYOUT_PATH=/foss/pdks/gf180mcuD/libs.tech/klayout:/foss/pdks/gf180mcuD/libs.tech/klayout/tech; "
               "klayout -v; klayout -b -r /foss/pdks/gf180mcuD/libs.tech/klayout/tech/drc/gf180mcu.drc "
               f"-rd input=/work/in.gds -rd topcell={top} -rd report={rep} -rd decks='{DECKS[deck]}' "
               f"-rd variant=D -rd run_mode=deep -rd threads={threads} -rd workers=1")
        with open(work / f"{deck}.log", "w") as log:
            p = subprocess.run(["docker", "run", "--rm", "--network", "none", "--cpus", str(threads),
                                "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp",
                                "-v", f"{work}:/work", "--entrypoint", "/bin/bash", IMAGE, "-lc", cmd],
                               stdout=log, stderr=subprocess.STDOUT)
        logtxt = (work / f"{deck}.log").read_text(errors="replace")
        ver = next((l.strip() for l in logtxt.splitlines() if l.startswith("KLayout")), "?")
        res["klayout"] = ver
        lyrdb = work / f"{deck}.lyrdb"
        if p.returncode != 0 or not lyrdb.exists():
            res["decks"][deck] = dict(error=f"klayout exit {p.returncode}", total=None)
            continue
        res["decks"][deck] = parse_lyrdb(lyrdb)
    local.unlink(missing_ok=True)
    res["clean"] = all(d.get("total") == 0 for d in res["decks"].values())
    (work / "kldrc.json").write_text(json.dumps(res, indent=1) + "\n")
    if do_publish:
        res["published"] = str(publish(res))
    summ = ", ".join(f"{k}={v.get('total')}" for k, v in res["decks"].items())
    print(f"{name}: {'CLEAN' if res['clean'] else 'FAIL'} ({summ})")
    for k, v in res["decks"].items():
        for r, n in list((v.get("rules") or {}).items())[:12]:
            print(f"  {k:8s} {r:22s} {n}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", action="append", default=[])
    ap.add_argument("--gds"); ap.add_argument("--top"); ap.add_argument("--name")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--decks", default="main,antenna")
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    decks = a.decks.split(",")
    out = pathlib.Path(a.out).resolve()
    jobs = []
    if a.gds:
        jobs.append((a.name or pathlib.Path(a.gds).stem, pathlib.Path(a.gds).resolve(), a.top))
    reg = json.loads(REGISTRY.read_text())["blocks"]
    for b in a.block:
        names = list(reg) if b == "all" else [b]
        for n in names:
            jobs.append((n, resolve(reg[n]["gds"]), reg[n]["top"]))
    if not jobs:
        ap.error("give --block or --gds/--top")
    ok = True
    for n, g, t in jobs:
        ok &= run(n, g, t, out, a.threads, decks, a.publish)["clean"]
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
