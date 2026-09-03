#!/usr/bin/env python3
"""Combine RewardKit graded scores with fail-closed gating."""

import argparse
import json
import math
from pathlib import Path


def load(path: str):
    try:
        value = json.loads(Path(path).read_text())
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and 0.0 <= value <= 1.0 else None


def details_ok(reward_path: str) -> bool:
    details = load(str(Path(reward_path).with_name("reward-details.json")))
    if not details:
        return False
    found = 0
    stack = [details]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if "criteria" in node:
                rows = node["criteria"] or []
                if not isinstance(rows, list):
                    return False
                for row in rows:
                    if not isinstance(row, dict) or row.get("error") or number(row.get("value")) is None:
                        return False
                    found += 1
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return found > 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graded", required=True)
    parser.add_argument("--graded-rc", type=int, required=True)
    parser.add_argument("--gating", required=True)
    parser.add_argument("--gating-rc", type=int, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    graded, gating = load(args.graded), load(args.gating)
    soft = number((graded or {}).get("reward"))
    gate_values = [number(value) for value in (gating or {}).values()]
    graded_ok = args.graded_rc == 0 and soft is not None and details_ok(args.graded)
    gating_ok = (args.gating_rc == 0 and bool(gate_values)
                 and all(value is not None for value in gate_values) and details_ok(args.gating))
    veto = gating_ok and min(gate_values) < 1.0
    unavailable = not (graded_ok and gating_ok)
    result = {
        "graded_score": soft or 0.0,
        "gating": 0.0 if veto else 1.0,
        "reward": 0.0 if veto or unavailable else soft,
        "verifier_error": 1.0 if unavailable else 0.0,
        "gating_unavailable": 0.0 if gating_ok else 1.0,
    }
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
