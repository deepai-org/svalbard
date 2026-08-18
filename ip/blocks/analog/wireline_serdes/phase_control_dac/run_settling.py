#!/usr/bin/env python3
"""Measure worst-carry DAC settling with realistic PI-control gate load."""
from __future__ import annotations
import argparse, concurrent.futures, json, math, re, subprocess
from pathlib import Path
from run_dc import ENVIRONMENTS, PORTS, instantiate

EDGE=10e-9
def source(name: str, initial: int, final: int, vdd: float) -> str:
    a=vdd if initial else 0.0; b=vdd if final else 0.0
    return f"V{name} {name} 0 PWL(0 {a:.3f} 9.995n {a:.3f} 10.005n {b:.3f} 100n {b:.3f})"
def sources(vdd: float) -> str:
    lines=[]
    for channel,old,new in (("A",15,16),("B",16,15)):
        for bit in range(4,-1,-1):
            oi=(old>>bit)&1; ni=(new>>bit)&1
            lines += [source(f"{channel}{bit}",oi,ni,vdd),source(f"{channel}{bit}B",1-oi,1-ni,vdd)]
    return "\n".join(lines)
def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--source",required=True,type=Path); p.add_argument("--pex",required=True,type=Path)
    p.add_argument("--work",required=True,type=Path); p.add_argument("--output",required=True,type=Path); p.add_argument("--jobs",type=int,default=4); args=p.parse_args()
    args.work.mkdir(parents=True,exist_ok=True); template=(args.source/"settling_tb.spice.in").read_text(); specs=[]
    for mos,res,vdd,temp in ENVIRONMENTS:
        case_id=f"{mos}_{res}_{vdd:.2f}_{temp:+d}".replace("+","p").replace("-","m").replace(".","p")
        wave=args.work/f"{case_id}.dat"; values={"MOS_CORNER":mos,"RES_CORNER":res,"TEMP_C":str(temp),"VDD_V":f"{vdd:.2f}",
          "DUT_PATH":str(args.pex),"DUT_SUBCKT":"phase_control_dac_pex","DUT_PORTS":" ".join(PORTS),"BIT_SOURCES":sources(vdd),"WAVE_PATH":str(wave)}
        specs.append((case_id,[mos,res,vdd,temp],wave,values))
    def simulate(spec):
        case_id,env,wave,values=spec; deck=args.work/f"{case_id}.spice"; log=args.work/f"{case_id}.log"; deck.write_text(instantiate(template,values))
        with log.open("w") as out: rc=subprocess.run(["ngspice","-b",str(deck)],stdout=out,stderr=subprocess.STDOUT,timeout=120,check=False).returncode
        rows=[]
        if wave.exists():
            for line in wave.read_text().splitlines():
                try: row=[float(x) for x in line.split()]
                except ValueError: continue
                if len(row)>=4: rows.append((row[0],row[1],row[3]))
        if not rows: return {"environment":env,"complete":False,"result":"fail"}
        initial_a=sum(r[1] for r in rows if 8e-9<=r[0]<=9e-9)/sum(8e-9<=r[0]<=9e-9 for r in rows)
        initial_b=sum(r[2] for r in rows if 8e-9<=r[0]<=9e-9)/sum(8e-9<=r[0]<=9e-9 for r in rows)
        final_a=sum(r[1] for r in rows if 90e-9<=r[0]<=100e-9)/sum(90e-9<=r[0]<=100e-9 for r in rows)
        final_b=sum(r[2] for r in rows if 90e-9<=r[0]<=100e-9)/sum(90e-9<=r[0]<=100e-9 for r in rows)
        settle=None
        for i,(t,a,b) in enumerate(rows):
            if t<EDGE: continue
            if all(abs(x[1]-final_a)<=0.002 and abs(x[2]-final_b)<=0.002 for x in rows[i:]): settle=t-EDGE; break
        post=[r for r in rows if r[0]>=EDGE]
        lo=min(min(r[1],r[2]) for r in post); hi=max(max(r[1],r[2]) for r in post)
        passed=rc==0 and settle is not None and settle<=25e-9 and lo>=0.25 and hi<=1.35 and abs(final_a-initial_b)<=0.010 and abs(final_b-initial_a)<=0.010
        return {"environment":env,"complete":rc==0,"initial_v":[initial_a,initial_b],"final_v":[final_a,final_b],
                "settling_time_s":settle,"transient_range_v":[lo,hi],"waveform_points":len(rows),"result":"pass" if passed else "fail"}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex: cases=list(ex.map(simulate,specs))
    result={"schema_version":1,"result":"pass" if all(c["result"]=="pass" for c in cases) else "fail","case_count":len(cases),
            "passing_case_count":sum(c["result"]=="pass" for c in cases),"cases":cases}
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); print(f"phase-control DAC settling: {result['passing_case_count']}/{len(cases)} pass")
    if result["result"]!="pass": raise SystemExit(1)
if __name__=="__main__": main()
