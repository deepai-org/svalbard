#!/usr/bin/env python3
"""Fail-closed numeric primitives shared by analog evidence checkers."""
from __future__ import annotations

import hashlib
import itertools
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")
EnvironmentKey = tuple[Any, ...]
Interval = tuple[float, float]


class EvidenceError(ValueError):
    """Raised when evidence cannot support the requested composition."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment_key(record: Mapping[str, Any]) -> EnvironmentKey:
    raw = record.get("environment")
    if not isinstance(raw, (list, tuple)) or not raw:
        raise EvidenceError("environment must be a non-empty sequence")
    try:
        key = tuple(raw)
        hash(key)
    except TypeError as error:
        raise EvidenceError("environment values must be hashable") from error
    return key


def environment_index(
    records: Iterable[Mapping[str, Any]],
) -> dict[EnvironmentKey, Mapping[str, Any]]:
    indexed: dict[EnvironmentKey, Mapping[str, Any]] = {}
    for record in records:
        key = environment_key(record)
        if key in indexed:
            raise EvidenceError(f"duplicate environment: {key!r}")
        indexed[key] = record
    if not indexed:
        raise EvidenceError("environment set is empty")
    return indexed


def require_same_environment_keys(
    indexes: Sequence[Mapping[EnvironmentKey, Any]],
    *,
    expected_count: int | None = None,
) -> set[EnvironmentKey]:
    if not indexes:
        raise EvidenceError("no environment sets supplied")
    expected = set(indexes[0])
    if expected_count is not None and len(expected) != expected_count:
        raise EvidenceError(
            f"expected {expected_count} environments, got {len(expected)}"
        )
    if any(set(index) != expected for index in indexes[1:]):
        raise EvidenceError("environment sets differ")
    return expected


def merge_intervals(intervals: Iterable[tuple[float, float]]) -> list[list[float]]:
    normalized: list[Interval] = []
    for first, second in intervals:
        lower, upper = sorted((float(first), float(second)))
        if not math.isfinite(lower) or not math.isfinite(upper):
            raise EvidenceError("interval endpoints must be finite")
        normalized.append((lower, upper))
    merged: list[list[float]] = []
    for lower, upper in sorted(normalized):
        if not merged or lower > merged[-1][1]:
            merged.append([lower, upper])
        else:
            merged[-1][1] = max(merged[-1][1], upper)
    return merged


def covers_value(intervals: Iterable[tuple[float, float]], value: float) -> bool:
    point = float(value)
    if not math.isfinite(point):
        raise EvidenceError("coverage point must be finite")
    return any(lower <= point <= upper for lower, upper in merge_intervals(intervals))


def covers_band(
    intervals: Iterable[tuple[float, float]], lower: float, upper: float,
) -> bool:
    band_lower, band_upper = float(lower), float(upper)
    if not math.isfinite(band_lower) or not math.isfinite(band_upper):
        raise EvidenceError("coverage band must be finite")
    if band_lower > band_upper:
        raise EvidenceError("coverage band endpoints are reversed")
    return any(
        interval_lower <= band_lower and interval_upper >= band_upper
        for interval_lower, interval_upper in merge_intervals(intervals)
    )


def require_unique_sha256(
    digests: Iterable[str], *, expected_count: int | None = None,
) -> tuple[str, ...]:
    values = tuple(digests)
    if expected_count is not None and len(values) != expected_count:
        raise EvidenceError(f"expected {expected_count} digests, got {len(values)}")
    invalid = [
        value
        for value in values
        if not isinstance(value, str) or not SHA256.fullmatch(value)
    ]
    if invalid:
        raise EvidenceError("invalid SHA-256 digest")
    if len(set(values)) != len(values):
        raise EvidenceError("physical evidence contains duplicate SHA-256 identities")
    return values


def minimum_covering_members(
    members: Mapping[
        str, Mapping[EnvironmentKey, Iterable[tuple[float, float]]]
    ],
    *,
    lower: float,
    upper: float,
) -> tuple[str, ...]:
    if not members:
        raise EvidenceError("no bank members supplied")
    names = tuple(members)
    environment_keys = require_same_environment_keys(
        [members[name] for name in names]
    )
    for count in range(1, len(names) + 1):
        for selected in itertools.combinations(names, count):
            if all(
                covers_band(
                    (
                        interval
                        for name in selected
                        for interval in members[name][environment]
                    ),
                    lower,
                    upper,
                )
                for environment in environment_keys
            ):
                return selected
    raise EvidenceError("no member subset continuously covers the requested band")
