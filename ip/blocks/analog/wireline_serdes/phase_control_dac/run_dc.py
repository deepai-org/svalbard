#!/usr/bin/env python3
"""Verify dual R-2R transfer monotonicity across representative GF180 PVT."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, re, subprocess
from pathlib import Path

ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27),
    ("ff", "res_ff", 2.97, -40), ("ff", "res_ss", 2.97, 125),
    ("ff", "res_typical", 3.63, -40), ("ff", "res_ff", 3.63, 125),
    ("ss", "res_ss", 2.97, -40), ("ss", "res_ff", 2.97, 125),
    ("ss", "res_typical", 3.63, -40), ("ss", "res_ss", 3.63, 125),
)
SCALAR = re.compile(r"^(ctrl_a|ctrl_b|reference_power)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
PORTS = tuple(f"{channel}{bit}{suffix}" for channel in "AB" for bit in range(4,-1,-1) for suffix in ("","B"))

def instantiate(template: str, values: dict[str,str]) -> str:
    for name,value in values.items(): template=template.replace(f"@{name}@",value)
    remaining=sorted(set(re.findall(r"@[A-Z0-9_]+@",template)))
    if remaining: raise ValueError(f"unfilled tokens: {remaining}")
    return template

def bit_sources(code_a: int, code_b: int, vdd: float) -> str:
    lines=[]
    for channel,code in (("A",code_a),("B",code_b)):
        for bit in range(4,-1,-1):
            value=(code>>bit)&1
            lines.append(f"V{channel}{bit} {channel}{bit} 0 {vdd if value else 0:.3f}")
            lines.append(f"V{channel}{bit}B {channel}{bit}B 0 {0 if value else vdd:.3f}")
    return "\n".join(lines)

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--source",required=True,type=Path); p.add_argument("--pex",type=Path)
    p.add_argument("--work",required=True,type=Path); p.add_argument("--output",required=True,type=Path)
    p.add_argument("--jobs",type=int,default=4); p.add_argument("--timeout-s",type=int,default=60); args=p.parse_args()
    if not 1<=args.jobs<=4: p.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True,exist_ok=True); dut=args.pex if args.pex else args.source/"phase_control_dac.spice"
    digest=hashlib.sha256(dut.read_bytes()).hexdigest(); template=(args.source/"dc_tb.spice.in").read_text(); specs=[]
    for env in ENVIRONMENTS:
        mos,res,vdd,temp=env
        for code in range(32):
            case_id=f"{mos}_{res}_{vdd:.2f}_{temp:+d}_c{code:02d}".replace("+","p").replace("-","m").replace(".","p")
            values={"DUT_SHA256":digest,"DUT_PATH":str(dut),"DUT_SUBCKT":"phase_control_dac_pex" if args.pex else "phase_control_dac",
                    "MOS_CORNER":mos,"RES_CORNER":res,"VDD_V":f"{vdd:.2f}","TEMP_C":str(temp),
                    "BIT_SOURCES":bit_sources(code,31-code,vdd),"DUT_PORTS":" ".join(PORTS)}
            specs.append((case_id,list(env),code,values))
    def simulate(spec):
        case_id,env,code,values=spec; deck=args.work/f"{case_id}.spice"; log=args.work/f"{case_id}.log"
        deck.write_text(instantiate(template,values))
        with log.open("w") as out:
            try: rc=subprocess.run(["ngspice","-b",str(deck)],stdout=out,stderr=subprocess.STDOUT,timeout=args.timeout_s,check=False).returncode
            except subprocess.TimeoutExpired: rc=124
        obs={k:float(v) for k,v in SCALAR.findall(log.read_text())}; complete=rc==0 and len(obs)==3
        return {"id":case_id,"environment":env,"code":code,"complete":complete,"ctrl_a_v":obs.get("ctrl_a"),
                "ctrl_b_v":obs.get("ctrl_b"),"reference_power_w":obs.get("reference_power"),"result":"complete" if complete else "incomplete"}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex: cases=list(ex.map(simulate,specs))
    groups=[]
    for env in map(list,ENVIRONMENTS):
        members=sorted((c for c in cases if c["environment"]==env),key=lambda c:c["code"])
        a=[c["ctrl_a_v"] for c in members]; b=[c["ctrl_b_v"] for c in members]
        steps_a=[y-x for x,y in zip(a,a[1:])]; steps_b=[x-y for x,y in zip(b,b[1:])]
        complement=[x+y for x,y in zip(a,b)]; powers=[c["reference_power_w"] for c in members]
        passed=(len(members)==32 and all(c["complete"] for c in members) and min(steps_a)>=0.020 and min(steps_b)>=0.020
                and a[0]<=0.335 and b[-1]<=0.335 and a[-1]>=1.24 and b[0]>=1.24
                and max(complement)-min(complement)<=0.020 and max(abs(x) for x in powers)<=0.005)
        groups.append({"environment":env,"minimum_step_a_v":min(steps_a),"minimum_step_b_v":min(steps_b),
                       "endpoint_low_v":max(a[0],b[-1]),"endpoint_high_v":min(a[-1],b[0]),
                       "complement_sum_range_v":[min(complement),max(complement)],"maximum_abs_reference_power_w":max(abs(x) for x in powers),
                       "result":"pass" if passed else "fail"})
    complete=sum(c["complete"] for c in cases); passing=sum(g["result"]=="pass" for g in groups)
    result={"schema_version":1,"mode":"extracted" if args.pex else "schematic","dut_sha256":digest,
            "result":"pass" if complete==len(cases) and passing==len(groups) else "fail","case_count":len(cases),
            "complete_case_count":complete,"group_count":len(groups),"passing_group_count":passing,"groups":groups,"cases":cases}
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(f"phase-control DAC: {complete}/{len(cases)} complete; {passing}/{len(groups)} environments pass")
    if result["result"]!="pass": raise SystemExit(1)
if __name__=="__main__": main()
