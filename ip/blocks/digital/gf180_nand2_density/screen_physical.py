#!/usr/bin/env python3
"""Build, verify, extract, and nominally screen NAND2 physical sizes."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

SOURCE = Path("/src")
WORK = Path("/work/physical-screen")
MOS = "/foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"
DESIGN = "/foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice"
MAGICRC = "/foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc"
MEASURE = re.compile(r"^(tplh|tphl|trise|tfall)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)

# The minimum point plus a ratio/scale grid.  Widths are transistor total
# widths; every candidate keeps L=0.28 um and the same two-device row topology.
CANDIDATES = [(0.42, 0.42)] + [
    (wn, round(wn * ratio, 2))
    for wn in (0.42, 0.56, 0.70, 0.84, 1.05)
    for ratio in (1.5, 2.0, 2.5)
] + [(wn, round(2.0 * wn, 2)) for wn in (1.26, 1.47, 1.68, 2.10, 2.52, 3.15, 4.20)]


def run(command: list[str], log: Path, *, env: dict[str, str] | None = None) -> None:
    with log.open("w") as stream:
        result = subprocess.run(command, cwd=WORK, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=180, check=False)
    if result.returncode:
        raise RuntimeError(f"{' '.join(command)} failed; see {log}")


def schematic(cell: str, wn: float, wp: float) -> str:
    return f"""* Generated physical NAND2 sizing candidate.
.subckt {cell} A1 A2 ZN VDD VNW VPW VSS
XN1 ZN A2 NINT VPW nfet_03v3 w={wn}u l=0.28u
XN2 NINT A1 VSS VPW nfet_03v3 w={wn}u l=0.28u
XP1 ZN A1 VDD VNW pfet_03v3 w={wp}u l=0.28u
XP2 ZN A2 VDD VNW pfet_03v3 w={wp}u l=0.28u
.ends {cell}
"""


def deck(pex: Path, cell: str, pin: str) -> str:
    def inst(index: int, signal: str, output: str) -> str:
        a1, a2 = (signal, f"VDD{index}") if pin == "A1" else (f"VDD{index}", signal)
        return f"X{index} {a1} {a2} {output} VDD{index} VDD{index} 0 0 {cell}_pex"
    return f"""* Exact-PEX, identical-predecessor, identical-FO1 NAND2 timing.
.include {DESIGN}
.lib {MOS} typical
.lib {MOS} res_typical
.include {pex}
.temp 25
V0 VDD0 0 3.3
V1 VDD1 0 3.3
V2 VDD2 0 3.3
VIN IN 0 PULSE(0 3.3 1n 20p 20p 1n 2n)
{inst(0, 'IN', 'N0')}
{inst(1, 'N0', 'N1')}
{inst(2, 'N1', 'N2')}
.control
tran 1p 8n
meas tran tplh trig v(N0) val=1.65 fall=2 targ v(N1) val=1.65 rise=2
meas tran tphl trig v(N0) val=1.65 rise=2 targ v(N1) val=1.65 fall=2
meas tran trise trig v(N1) val=0.66 rise=2 targ v(N1) val=2.64 rise=2
meas tran tfall trig v(N1) val=2.64 fall=2 targ v(N1) val=0.66 fall=2
print tplh tphl trise tfall
.endc
.end
"""


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    physical: list[dict[str, object]] = []
    for wn, wp in CANDIDATES:
        tag = f"n{round(wn * 100):03d}_p{round(wp * 100):03d}"
        cell = f"nand2_{tag}"
        spice = WORK / f"{cell}.spice"
        spice.write_text(schematic(cell, wn, wp))
        env = os.environ.copy()
        env.update(NAND_CELL=cell, NAND_WN=str(wn), NAND_WP=str(wp))
        magic_log = WORK / f"{cell}.magic.log"
        run(["magic", "-dnull", "-noconsole", "-rcfile", MAGICRC,
             str(SOURCE / "layout.tcl")], magic_log, env=env)
        drc_dir = WORK / f"drc-{tag}"
        lvs_dir = WORK / f"lvs-{tag}"
        pex_dir = WORK / f"pex-{tag}"
        run(["sak-drc.sh", "-m", "-w", str(drc_dir), str(WORK / f"{cell}.mag")],
            WORK / f"{cell}.drc-stage.log")
        run(["sak-lvs.sh", "-m", "-w", str(lvs_dir), "-s", str(spice),
             "-l", str(WORK / f"{cell}.mag"), "-c", cell],
            WORK / f"{cell}.lvs-stage.log")
        run(["sak-pex.sh", "-m", "3", "-t", "0", "-r", "1", "-y", "0",
             "-n", f"{cell}_pex", "-w", str(pex_dir), str(WORK / f"{cell}.mag")],
            WORK / f"{cell}.pex-stage.log")
        lvs = next(lvs_dir.glob(f"{cell}.magic.lvs/{cell}.lvs.out"))
        pex = pex_dir / f"{cell}.pex.spice"
        magic_text = magic_log.read_text()
        lvs_text = lvs.read_text()
        physical.append({
            "tag": tag, "cell": cell, "wn_um": wn, "wp_um": wp,
            "width_um": 1.96, "height_um": round(1.91 + wn + wp, 6),
            "area_um2": round(1.96 * (1.91 + wn + wp), 6),
            "drc_errors": int(re.search(r"CUSTOM_DRC_COUNT\s+(\d+)", magic_text).group(1)),
            "lvs_unique": "Circuits match uniquely." in lvs_text,
            "pex": str(pex),
            "pex_sha256": hashlib.sha256(pex.read_bytes()).hexdigest(),
            "pex_resistors": len(re.findall(r"^R\d+\s", pex.read_text(), re.MULTILINE)),
            "pex_capacitors": len(re.findall(r"^C\d+\s", pex.read_text(), re.MULTILINE)),
        })

    jobs: list[tuple[dict[str, object], str]] = [(item, pin) for item in physical for pin in ("A1", "A2")]

    def simulate(job: tuple[dict[str, object], str]) -> dict[str, object]:
        item, pin = job
        path = WORK / f"{item['cell']}.{pin}.spice"
        log = WORK / f"{item['cell']}.{pin}.log"
        path.write_text(deck(Path(str(item["pex"])), str(item["cell"]), pin))
        run(["ngspice", "-b", str(path)], log)
        values = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
        return {"tag": item["tag"], "pin": pin, **{f"{key}_s": value for key, value in values.items()}}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        timing = list(pool.map(simulate, jobs))
    for item in physical:
        cases = [case for case in timing if case["tag"] == item["tag"]]
        item["arcs"] = cases
        item["worst_delay_s"] = max(max(float(case["tplh_s"]), float(case["tphl_s"])) for case in cases)
        item["worst_transition_s"] = max(max(float(case["trise_s"]), float(case["tfall_s"])) for case in cases)
        item["result"] = "pass" if item["drc_errors"] == 0 and item["lvs_unique"] and len(cases) == 2 else "fail"
    passing = [item for item in physical if item["result"] == "pass"]
    result = {
        "schema_version": 1,
        "claim": "exact_pex_fo1_physical_nand2_size_screen",
        "benchmark": "middle of three identical extracted stages; one identical gate input load",
        "candidate_count": len(physical),
        "smallest": min(passing, key=lambda item: float(item["area_um2"]))["tag"],
        "fastest": min(passing, key=lambda item: float(item["worst_delay_s"]))["tag"],
        "candidates": physical,
        "result": "pass" if len(passing) == len(physical) else "fail",
    }
    (Path("/work") / "physical-screen.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for item in sorted(passing, key=lambda candidate: float(candidate["worst_delay_s"])):
        print(f"{item['tag']} area={item['area_um2']:.4f}um2 delay={float(item['worst_delay_s'])*1e12:.3f}ps")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
