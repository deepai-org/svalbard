#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    data = json.loads((ROOT / "tests/coverage/coverage_manifest.json").read_text())
    reqs = data["requirements"]
    tests = data["scenarios"]
    req_ids = [row["id"] for row in reqs]
    test_ids = [row["id"] for row in tests]
    assert len(req_ids) == len(set(req_ids))
    assert len(test_ids) == len(set(test_ids))
    covered: set[str] = set()
    for test in tests:
        assert test["requirements"] and test["stimulus"] and test["observations"] and test["oracle"]
        unknown = set(test["requirements"]) - set(req_ids)
        assert not unknown, (test["id"], unknown)
        covered.update(test["requirements"])
    assert covered == set(req_ids), sorted(set(req_ids) - covered)
    print(f"coverage audit: PASS ({len(reqs)} requirements, {len(tests)} scenarios)")


if __name__ == "__main__":
    main()
