"""Small deterministic metric primitives used to qualify analog testbenches."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence


@dataclass(frozen=True)
class EyeMetrics:
    eye_height_v: float
    one_floor_v: float
    zero_ceiling_v: float
    sample_count: int


def differential(vp: Sequence[float], vn: Sequence[float]) -> list[float]:
    if len(vp) != len(vn) or not vp:
        raise ValueError("differential traces must be non-empty and equal length")
    out = [float(p) - float(n) for p, n in zip(vp, vn)]
    if not all(isfinite(value) for value in out):
        raise ValueError("trace contains a non-finite value")
    return out


def common_mode(vp: Sequence[float], vn: Sequence[float]) -> list[float]:
    if len(vp) != len(vn) or not vp:
        raise ValueError("common-mode traces must be non-empty and equal length")
    out = [(float(p) + float(n)) / 2.0 for p, n in zip(vp, vn)]
    if not all(isfinite(value) for value in out):
        raise ValueError("trace contains a non-finite value")
    return out


def center_sample_eye(diff: Sequence[float], bits: Sequence[int], samples_per_ui: int) -> EyeMetrics:
    """Measure center-sample vertical eye opening for an aligned fixture.

    Production benches must separately establish alignment and horizontal eye
    opening.  This deliberately narrow primitive prevents an optimizer from
    choosing its own favorable sample phase while qualifying the metric code.
    """
    if samples_per_ui < 2 or len(diff) != len(bits) * samples_per_ui:
        raise ValueError("trace length must equal bits * samples_per_ui")
    centers = [float(diff[i * samples_per_ui + samples_per_ui // 2]) for i in range(len(bits))]
    ones = [value for value, bit in zip(centers, bits) if bit == 1]
    zeros = [value for value, bit in zip(centers, bits) if bit == 0]
    if not ones or not zeros or any(bit not in (0, 1) for bit in bits):
        raise ValueError("eye measurement requires valid zero and one populations")
    one_floor = min(ones)
    zero_ceiling = max(zeros)
    return EyeMetrics(one_floor - zero_ceiling, one_floor, zero_ceiling, len(centers))


def threshold_crossings(times: Sequence[float], values: Sequence[float], threshold: float = 0.0) -> list[float]:
    if len(times) != len(values) or len(times) < 2:
        raise ValueError("crossing traces must have matching length >= 2")
    result: list[float] = []
    for t0, t1, v0, v1 in zip(times, times[1:], values, values[1:]):
        if t1 <= t0:
            raise ValueError("times must be strictly increasing")
        a, b = float(v0) - threshold, float(v1) - threshold
        if a == 0.0:
            result.append(float(t0))
        elif (a < 0.0 < b) or (a > 0.0 > b):
            result.append(float(t0) + (float(t1) - float(t0)) * (-a) / (b - a))
    return result
