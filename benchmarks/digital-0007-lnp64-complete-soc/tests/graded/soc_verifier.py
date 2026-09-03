from __future__ import annotations

import json
import math
import subprocess
import threading
from pathlib import Path

import rewardkit as rk

TESTS = Path("/tests")
LOG = Path("/logs/verifier/soc")
EVIDENCE = LOG / "evidence.json"
_condition = threading.Condition()
_running = False
_result: dict | None = None
_error: Exception | None = None


def level(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"{name} is not numeric")
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise RuntimeError(f"{name} is outside [0, 1]")
    return value


def execute(workspace: Path) -> dict:
    LOG.mkdir(parents=True, exist_ok=True)
    with (LOG / "release.log").open("w") as transcript:
        run = subprocess.run(
            ["python3", str(TESTS / "run_release.py"),
             "--candidate", str(workspace / "output"), "--log", str(LOG)],
            stdout=transcript, stderr=subprocess.STDOUT, timeout=85_000,
        )
    try:
        data = json.loads(EVIDENCE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("release verifier produced no valid evidence") from exc
    if data.get("schema_version") != 1 or data.get("benchmark") != "circuitbench-digital/6045-lnp64-complete-soc":
        raise RuntimeError("release evidence identity mismatch")
    if data.get("return_code") != run.returncode:
        raise RuntimeError("release evidence return code mismatch")
    return data


def result(workspace: Path) -> dict:
    global _running, _result, _error
    with _condition:
        while _running:
            _condition.wait()
        if _result is not None:
            return _result
        if _error is not None:
            raise RuntimeError("shared verifier execution failed") from _error
        _running = True
    try:
        value = execute(workspace)
    except Exception as exc:
        with _condition:
            _error, _running = exc, False
            _condition.notify_all()
        raise
    with _condition:
        _result, _running = value, False
        _condition.notify_all()
        return value


def criterion(workspace: Path, name: str) -> float:
    return level(result(workspace).get("criteria", {}).get(name), name)


@rk.criterion(description="LNP64 ISA, engine, SMP, boot, and device tests.", shared=True)
def architectural_and_platform_verification(workspace: Path) -> float:
    return criterion(workspace, "R1")


@rk.criterion(description="Routed GF180MCU implementation and mapped-netlist replay.", shared=True)
def gf180_physical_verification(workspace: Path) -> float:
    return criterion(workspace, "R2")


@rk.criterion(description="Measured post-route frequency, area, and power quality.", shared=True)
def measured_implementation_quality(workspace: Path) -> float:
    return criterion(workspace, "R3")


rk.architectural_and_platform_verification(weight=5.0, name="R1")
rk.gf180_physical_verification(weight=2.0, name="R2")
rk.measured_implementation_quality(weight=3.0, name="R3")
