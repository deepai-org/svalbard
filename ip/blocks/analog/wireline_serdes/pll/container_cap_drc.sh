#!/usr/bin/env bash
set -euo pipefail

cases=("0.35 4.0" "0.37 4.0" "0.38 4.0" "0.37 3.6" "0.37 3.2" "0.37 2.8")
for case in "${cases[@]}"; do
  read -r cap_l cap_w <<< "$case"
  tag="l${cap_l/./p}_w${cap_w/./p}"
  export VCO_CELL_NAME="cml_vco_cap_${tag}"
  export VCO_CAP_L="$cap_l"
  export VCO_CAP_W="$cap_w"
  export VCO_LOAD_L=6.25
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/layout.tcl > "/work/${tag}-layout.log" 2>&1
  sak-drc.sh -m -w "/work/${tag}-drc" "/work/${VCO_CELL_NAME}.mag" \
    > "/work/${tag}-drc-stage.log" 2>&1 || true
  cp "/work/${tag}-drc/${VCO_CELL_NAME}.magic.drc/${VCO_CELL_NAME}.magic.drc.rpt" \
    "/work/${tag}.rpt"
done

python3 - <<'PY'
import json
import re
from pathlib import Path
dimensions = (("0.35", "4.0"), ("0.37", "4.0"), ("0.38", "4.0"),
              ("0.37", "3.6"), ("0.37", "3.2"), ("0.37", "2.8"))
cases = []
for length, width in dimensions:
    tag = f"l{length.replace('.', 'p')}_w{width.replace('.', 'p')}"
    report = Path(f"/work/{tag}.rpt").read_text()
    match = re.search(r"\[INFO\] COUNT: (\d+)", report)
    count = int(match.group(1)) if match else None
    cases.append({"cap_length_um": float(length), "cap_width_um": float(width),
                  "drc_error_count": count,
                  "result": "pass" if count == 0 else "fail"})
result = {"schema_version": 1, "cell": "cml_vco_delay_cap_legality",
          "result": "pass" if all(case["result"] == "pass" for case in cases) else "partial",
          "cases": cases}
Path("/work/cap-drc.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print("cap DRC: " + ", ".join(f"{case['cap_length_um']:.2f}x{case['cap_width_um']:.1f}um={case['drc_error_count']}"
                               for case in cases))
if any(case["cap_length_um"] >= 0.37 and case["cap_width_um"] >= 3.2
       and case["result"] != "pass" for case in cases):
    raise SystemExit("interpolated cap geometry is not DRC clean")
PY
