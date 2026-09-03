#!/usr/bin/env python3
"""Mutation checks for the RewardKit result finalizer."""

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def write_reward(root: Path, name: str, reward: dict, values: list[float]) -> Path:
    directory = root / name
    directory.mkdir()
    path = directory / "reward.json"
    path.write_text(json.dumps(reward))
    (directory / "reward-details.json").write_text(json.dumps({
        "programmatic": {"criteria": [{"value": value, "weight": 1.0} for value in values]}
    }))
    return path


def finalize(root: Path, graded: Path, gating: Path, graded_rc: int = 0, gating_rc: int = 0) -> dict:
    output = root / "result.json"
    subprocess.run(["python3", str(ROOT / "tests/finalize.py"), "--graded", str(graded),
                    "--graded-rc", str(graded_rc), "--gating", str(gating),
                    "--gating-rc", str(gating_rc), "--out", str(output)], check=True)
    return json.loads(output.read_text())


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="lnp64-finalizer-") as temporary:
        root = Path(temporary)
        graded = write_reward(root, "graded", {"reward": 0.59}, [1, .5, .2])
        gating = write_reward(root, "gating", {"reward": 1.0}, [1, 1])
        good = finalize(root, graded, gating)
        assert good["reward"] == 0.59 and good["verifier_error"] == 0
        gating.write_text(json.dumps({"reward": 0.5}))
        veto = finalize(root, graded, gating)
        assert veto["reward"] == 0 and veto["gating"] == 0 and veto["verifier_error"] == 0
        (gating.parent / "reward-details.json").write_text("{}")
        broken = finalize(root, graded, gating)
        assert broken["reward"] == 0 and broken["verifier_error"] == 1
    print("RewardKit finalizer mutations: PASS")


if __name__ == "__main__":
    main()
