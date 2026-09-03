from __future__ import annotations

import json
import sys
from pathlib import Path

import rewardkit as rk

sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate_safety import check


@rk.criterion(description="Candidate files and frozen manifest pass the safety policy.", shared=True)
def candidate_policy(workspace: Path) -> bool:
    return not check(workspace / "output")


@rk.criterion(description="Every architectural, platform, and physical hard gate passed.", shared=True)
def complete_soc_hard_gates(workspace: Path) -> bool:
    del workspace
    path = Path("/logs/verifier/soc/evidence.json")
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("release evidence is unavailable") from exc
    if data.get("schema_version") != 1 or not isinstance(data.get("eligible"), bool):
        raise RuntimeError("release evidence is malformed")
    gates = data.get("hard_gates")
    if not isinstance(gates, dict) or not gates or not all(isinstance(v, bool) for v in gates.values()):
        raise RuntimeError("release hard-gate ledger is malformed")
    return data["eligible"] and all(gates.values())


rk.candidate_policy(weight=1.0, name="G1")
rk.complete_soc_hard_gates(weight=1.0, name="G2")
