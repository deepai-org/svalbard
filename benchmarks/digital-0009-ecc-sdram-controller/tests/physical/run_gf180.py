#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, os, shutil, subprocess
from pathlib import Path

HERE=Path(__file__).resolve()
ROOT=HERE.parents[2]
INPUT=Path("/app/input_files") if Path("/app/input_files").is_dir() else ROOT/"environment/input_files"
TESTS=Path("/tests") if Path("/tests").is_dir() else ROOT/"tests"
TOP="ecc_sdram_controller"
CORNER="nom_ss_125C_4v50"

def digest(path: Path) -> str:
    h=hashlib.sha256()
    for p in sorted(x for x in path.rglob("*") if x.is_file()):
        h.update(p.relative_to(path).as_posix().encode()+b"\0");h.update(p.read_bytes())
    return h.hexdigest()

def main() -> None:
    ap=argparse.ArgumentParser();ap.add_argument("candidate",type=Path)
    ap.add_argument("--work",type=Path,required=True);ap.add_argument("--jobs",type=int,default=4)
    ap.add_argument("--prepare-only",action="store_true");args=ap.parse_args()
    candidate=args.candidate.resolve();rtl=candidate/f"rtl/{TOP}.sv"
    if not rtl.is_file():raise SystemExit("missing required RTL")
    work=args.work.resolve()
    if work.exists():shutil.rmtree(work)
    work.mkdir(parents=True)
    config={
      "meta":{"version":3,"flow":"Classic"},"DESIGN_NAME":TOP,
      "VERILOG_FILES":[str(rtl)],"STD_CELL_LIBRARY":"gf180mcu_fd_sc_mcu9t5v0",
      "CLOCK_PORT":"clk_i","CLOCK_PERIOD":10.0,
      "PNR_SDC_FILE":str((INPUT/f"constraints/{TOP}.sdc").resolve()),
      "SIGNOFF_SDC_FILE":str((INPUT/f"constraints/{TOP}.sdc").resolve()),
      "DEFAULT_CORNER":CORNER,"STA_CORNERS":[CORNER],
      "SYNTH_STRATEGY":"DELAY 3","PL_TARGET_DENSITY_PCT":30,
      "SYNTH_TRISTATE_MAP":str((INPUT/"tools/gf180_tristate_map.v").resolve()),
      "FP_SIZING":"relative","FP_CORE_UTIL":25,"GRT_ALLOW_CONGESTION":True,
      "RT_MAX_LAYER":"Metal5","DRT_THREADS":max(1,min(args.jobs,16)),"DRT_ANTENNA_REPAIR_ITERS":4
    }
    cfg=work/"config.json";cfg.write_text(json.dumps(config,indent=2)+"\n")
    if args.prepare_only:
        print(cfg);return
    cmd=["librelane","--manual-pdk","--pdk-root",os.environ.get("PDK_ROOT","/foss/pdks"),
      "-p","gf180mcuD","-s","gf180mcu_fd_sc_mcu9t5v0","-j",str(args.jobs),
      "--condensed","--hide-progress-bar","--to","OpenROAD.STAPostPNR",
      "--run-tag","candidate",str(cfg)]
    env=os.environ.copy();env["PATH"]="/foss/tools/bin:/foss/tools/klayout:"+env.get("PATH","")
    env["LD_LIBRARY_PATH"]="/foss/tools/iverilog/lib:/foss/tools/klayout:/foss/tools/ngspice/lib:"+env.get("LD_LIBRARY_PATH","")
    with (work/"librelane.log").open("w") as log:
        run=subprocess.run(cmd,cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT)
    if run.returncode:
        print("\n".join((work/"librelane.log").read_text(errors="replace").splitlines()[-100:]))
        raise SystemExit("LibreLane failed")
    final=work/"runs/candidate/final";m=json.loads((final/"metrics.json").read_text())
    wns=float(m.get(f"timing__setup__wns__corner:{CORNER}",float("-inf")))
    vio=int(m.get(f"timing__setup_vio__count__corner:{CORNER}",-1))
    drc=int(m.get("route__drc_errors",-1))
    area=float(m.get("design__instance__area__stdcell",float("nan")))
    route=all((final/k/f"{TOP}.{ext}").is_file() for k,ext in (("def","def"),("odb","odb"),("nl","nl.v")))
    mapped=False
    if route:
        pdk=Path(os.environ.get("PDK_ROOT","/foss/pdks"))/"gf180mcuD"
        cell_dir=pdk/"libs.ref/gf180mcu_fd_sc_mcu9t5v0/verilog"
        sim=work/"mapped.vvp";sim_log=work/"mapped.log"
        compile_run=subprocess.run(["iverilog","-g2012","-gno-specify","-DFUNCTIONAL",
          "-s","tb_mapped","-o",str(sim),str(cell_dir/"primitives.v"),
          str(cell_dir/"gf180mcu_fd_sc_mcu9t5v0.v"),str(final/"nl"/f"{TOP}.nl.v"),
          str(TESTS/"assets/tb_mapped.sv")],env=env,text=True,capture_output=True)
        if compile_run.returncode==0:
            sim_run=subprocess.run(["vvp",str(sim)],env=env,text=True,capture_output=True)
            sim_log.write_text(compile_run.stdout+compile_run.stderr+sim_run.stdout+sim_run.stderr)
            mapped=sim_run.returncode==0 and "MAPPED_PASS" in sim_run.stdout
        else:sim_log.write_text(compile_run.stdout+compile_run.stderr)
    evidence={"schema_version":1,"candidate_digest":digest(candidate),"pdk":"GF180MCU/gf180mcuD",
      "library":"gf180mcu_fd_sc_mcu9t5v0","corner":CORNER,"route_complete":route,
      "mapped_gate_passed":mapped,
      "route_drc_errors":drc,"setup_wns_ns":wns,"setup_violation_count":vio,
      "area_um2":area,"estimated_fmax_mhz":1000.0/(10.0-wns) if 10.0-wns>0 else 0.0}
    evidence["eligible"]=route and mapped and drc==0 and vio==0 and wns>=0 and math.isfinite(area) and area>0
    (work/"physical_evidence.json").write_text(json.dumps(evidence,indent=2,sort_keys=True)+"\n")
    print(json.dumps(evidence,sort_keys=True))
    if not evidence["eligible"]:raise SystemExit("GF180 physical eligibility failed")
if __name__=="__main__":main()
