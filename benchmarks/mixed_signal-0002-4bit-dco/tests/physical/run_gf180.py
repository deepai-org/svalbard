#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT=Path(__file__).resolve().parents[2]
PINS={"EN","CTRL0","CTRL1","CTRL2","CTRL3","OUT","VDD","VSS"}
DENSITY_WAIVERS={"DCF.1b","M1.4","M2.4","M3.4","M4.4","M5.4","MT.3"}


def run(command:list[str],log:Path,**kwargs)->subprocess.CompletedProcess:
    result=subprocess.run(command,text=True,capture_output=True,**kwargs)
    log.write_text(result.stdout+result.stderr)
    return result


def main()->None:
    ap=argparse.ArgumentParser();ap.add_argument("candidate",type=Path)
    ap.add_argument("--work",type=Path,required=True);ap.add_argument("--jobs",type=int,default=4)
    args=ap.parse_args();candidate=args.candidate.resolve();work=args.work.resolve()
    if work.exists():shutil.rmtree(work)
    work.mkdir(parents=True)
    spice=candidate/"analog/dco4.spice";gds=candidate/"layout/dco4.gds"
    manifest=candidate/"integration/dco4.json"
    expected={"top":"dco4","pins":["EN","CTRL0","CTRL1","CTRL2","CTRL3","OUT","VDD","VSS"],"supply_v":3.3}
    if json.loads(manifest.read_text())!=expected:raise SystemExit("manifest mismatch")
    if not re.search(r"(?im)^\.subckt\s+dco4\s+EN\s+CTRL0\s+CTRL1\s+CTRL2\s+CTRL3\s+OUT\s+VDD\s+VSS\s*$",spice.read_text()):
        raise SystemExit("SPICE signature mismatch")

    pdk=Path(os.environ.get("PDK_ROOT","/foss/pdks"))/"gf180mcuD"
    env=os.environ.copy();env["PATH"]="/foss/tools/bin:/foss/tools/klayout:"+env.get("PATH","")
    env["LD_LIBRARY_PATH"]="/foss/tools/klayout:/foss/tools/ngspice/lib:"+env.get("LD_LIBRARY_PATH","")
    inspect_py=work/"inspect.py";inspect_json=work/"inspect.json"
    inspect_py.write_text(f'''import json, pya
layout=pya.Layout(); layout.read({str(gds)!r})
tops=[c.name for c in layout.top_cells()]
cell=layout.cell("dco4"); labels=set()
if cell:
  for layer in layout.layer_indices():
    for shape in cell.shapes(layer).each():
      if shape.is_text(): labels.add(shape.text.string)
bbox=cell.bbox() if cell else pya.Box()
json.dump({{"tops":tops,"labels":sorted(labels),"area_um2":bbox.width()*bbox.height()*layout.dbu*layout.dbu}},open({str(inspect_json)!r},"w"))
''')
    inspect=run(["klayout","-b","-r",str(inspect_py)],work/"inspect.log",env=env)
    if inspect.returncode or not inspect_json.is_file():raise SystemExit("KLayout GDS inspection failed")
    info=json.loads(inspect_json.read_text());tops=info["tops"];labels=set(info["labels"])
    if tops!=["dco4"]:raise SystemExit(f"GDS top mismatch: {tops}")
    if not PINS<=labels:raise SystemExit(f"missing top-level GDS pins: {sorted(PINS-labels)}")
    area_um2=float(info["area_um2"])
    drc_db=work/"drc.lyrdb"
    drc=run(["klayout","-b","-r",str(pdk/"libs.tech/klayout/tech/drc/gf180mcu.drc"),
      "-rd",f"input={gds}","-rd",f"report={drc_db}","-rd","topcell=dco4",
      "-rd","variant=gf180mcuD","-rd","run_mode=deep","-rd","workers=1",
      "-rd",f"threads={max(1,args.jobs)}"],work/"drc.log",env=env)
    if drc.returncode or not drc_db.is_file():raise SystemExit("KLayout DRC failed")
    violations=[]
    for item in ET.parse(drc_db).getroot().findall(".//items/item"):
        category=(item.findtext("category") or "").strip("'\"")
        violations.append(category)
    non_density=[v for v in violations if v not in DENSITY_WAIVERS]
    if non_density:raise SystemExit(f"non-density DRC violations: {non_density}")

    hier_tcl=work/"extract_lvs.tcl";hier=work/"dco4_lvs.spice"
    hier_tcl.write_text(f"""crashbackups stop
gds readonly true
gds rescale false
gds read {gds}
load dco4
select top cell
extract do local
extract unique all
extract all
ext2spice hierarchy on
ext2spice subcircuit top on
ext2spice cthresh infinite
ext2spice rthresh infinite
ext2spice -o {hier}
quit -noprompt
""")
    magic_lvs=run(["magic","-dnull","-noconsole","-rcfile",str(pdk/"libs.tech/magic/gf180mcuD.magicrc"),str(hier_tcl)],work/"extract_lvs.log",env=env,cwd=work)
    if magic_lvs.returncode or not hier.is_file():raise SystemExit("Magic LVS extraction failed")
    cell_spice=pdk/"libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice"
    def blackbox_cells(text:str)->str:
        pattern=re.compile(r"(?ims)^\.subckt\s+(gf180mcu_fd_sc_mcu7t5v0__\S+)[^\r\n]*.*?^\.ends[^\r\n]*")
        return pattern.sub(lambda m: m.group(0).splitlines()[0]+"\n.ends "+m.group(1),text)
    def headers(text:str)->dict[str,list[str]]:
        return {m.group(1):m.group(2).split() for m in re.finditer(r"(?im)^\.subckt\s+(\S+)\s+([^\r\n]+)",text)}
    hier_text=hier.read_text();cell_text=cell_spice.read_text()
    extracted_headers=headers(hier_text);pdk_headers=headers(cell_text)
    pdk_blackboxes=work/"gf180_cells_blackbox.spice"
    pdk_blackboxes.write_text(blackbox_cells(cell_text))
    top_text=hier_text.split(".subckt dco4 ",1)[1].split(".ends",1)[0]
    top_text="\n".join(top_text.splitlines()[1:])
    normalized=[".subckt dco4 EN CTRL0 CTRL1 CTRL2 CTRL3 OUT VDD VSS"]
    for line in top_text.splitlines():
        fields=line.split()
        if not fields:continue
        cell=fields[-1]
        if cell.startswith("gf180mcu_fd_sc_mcu7t5v0__"):
            old_pins=extracted_headers[cell];new_pins=pdk_headers[cell];nodes=fields[1:-1]
            if len(old_pins)!=len(nodes) or set(old_pins)!=set(new_pins):raise SystemExit(f"cannot normalize {cell}")
            by_pin=dict(zip(old_pins,nodes));line=" ".join([fields[0]]+[by_pin[p] for p in new_pins]+[cell])
        normalized.append(line)
    normalized.append(".ends dco4")
    layout_structural=work/"dco4_lvs_structural.spice"
    layout_structural.write_text(pdk_blackboxes.read_text()+"\n"+"\n".join(normalized)+"\n")
    reference=work/"dco4_lvs_reference.spice"
    reference.write_text(spice.read_text())
    lvs_report=work/"lvs.rpt";lvs_script=work/"lvs.tcl";netgen_env=work/"netgen_env.tcl"
    netgen_env.write_text(f"set ::env(NETGEN_SETUP) {pdk}/libs.tech/netgen/gf180mcuD_setup.tcl\n")
    lvs_script.write_text(f'''set circuit1 [readnet spice {layout_structural}]
set circuit2 [readnet spice /dev/null]
readnet spice {pdk_blackboxes} $circuit2
readnet spice {reference} $circuit2
lvs "$circuit1 dco4" "$circuit2 dco4" /usr/local/lib/python3.12/dist-packages/librelane/scripts/netgen/setup.tcl {lvs_report} -blackbox -json
quit
''')
    lvs_env=env.copy();lvs_env["_TCL_ENV_IN"]=str(netgen_env);lvs_env["NETGEN_SETUP"]=str(pdk/"libs.tech/netgen/gf180mcuD_setup.tcl")
    lvs=run(["netgen","-batch","source",str(lvs_script)],work/"lvs.log",env=lvs_env,cwd=work)
    lvs_text=(work/"lvs.log").read_text(errors="replace")
    if lvs.returncode or "Circuits match uniquely." not in lvs_text or "Property errors were found." in lvs_text:
        raise SystemExit("LVS mismatch")

    tcl=work/"extract_pex.tcl";pex=work/"dco4_pex.spice"
    tcl.write_text(f"""crashbackups stop
gds readonly true
gds rescale false
gds read {gds}
load dco4
flatten dco4_pex
load dco4_pex
select top cell
extract do local
extract unique all
extract all
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice -o {pex}
quit -noprompt
""")
    magic=run(["magic","-dnull","-noconsole","-rcfile",str(pdk/"libs.tech/magic/gf180mcuD.magicrc"),str(tcl)],work/"extract_pex.log",env=env,cwd=work)
    if magic.returncode or not pex.is_file():raise SystemExit("Magic PEX failed")

    header=re.search(r"(?im)^\.subckt\s+dco4_pex\s+([^\r\n]+)",pex.read_text())
    if not header:raise SystemExit("PEX top signature missing")
    pex_text=re.sub(r"\s+\*\*FLOATING\b","",pex.read_text(),flags=re.I).replace(".subckt dco4_pex", ".subckt dco4_extracted",1)
    pex_text += f"\n.subckt dco4 EN CTRL0 CTRL1 CTRL2 CTRL3 OUT VDD VSS\nXPEX {header.group(1)} dco4_extracted\n.ends dco4\n"
    pex_candidate=work/"pex_candidate/analog";pex_candidate.mkdir(parents=True)
    (pex_candidate/"dco4.spice").write_text(pex_text)
    pex_json=work/"pex_tt.json"
    char_env=env.copy();char_env.update({"OMP_NUM_THREADS":"1","OMP_THREAD_LIMIT":"1"})
    char=run(["python3",str(ROOT/"tests/characterize.py"),str(pex_candidate.parent),"--tt-only","--pex-sample",
      "--json",str(pex_json),"--jobs",str(max(1,min(args.jobs,4)))],work/"pex_characterize.log",env=char_env,cwd=work)
    if char.returncode or not pex_json.is_file():raise SystemExit("PEX TT characterization failed")

    evidence={"schema_version":1,"pdk":"GF180MCU/gf180mcuD","top":"dco4",
      "pins":sorted(PINS),"area_um2":area_um2,"drc_non_density_errors":len(non_density),
      "deferred_global_density_rules":sorted(set(violations)&DENSITY_WAIVERS),
      "lvs_passed":True,"pex_tt_passed":True}
    (work/"physical_evidence.json").write_text(json.dumps(evidence,indent=2,sort_keys=True)+"\n")
    print(json.dumps(evidence,sort_keys=True))


if __name__=="__main__":main()
