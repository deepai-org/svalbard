#!/usr/bin/env python3
import json
import math
import tempfile
from pathlib import Path

from run_gf180 import CORNER, parse_result


def fixture(root: Path) -> Path:
    final = root / "runs/candidate/final"
    for relative in ("def/lnp64_soc.def", "odb/lnp64_soc.odb", "nl/lnp64_soc.nl.v"):
        path = final / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
    metrics = {
        f"timing__setup__wns__corner:{CORNER}": 0.125,
        f"timing__setup_vio__count__corner:{CORNER}": 0,
        "route__drc_errors": 0,
        "design__instance__area__stdcell": 1000.0,
        "design__instance__area__macros": 234.5,
        "power__total": 0.25,
    }
    (final / "metrics.json").write_text(json.dumps(metrics))
    return final / "metrics.json"


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        metrics_path = fixture(root)
        assert parse_result(root, "a" * 64, 8, True)["eligible"] is True
        baseline = json.loads(metrics_path.read_text())
        for field, value in (
            ("route__drc_errors", 1),
            (f"timing__setup__wns__corner:{CORNER}", -0.001),
            (f"timing__setup_vio__count__corner:{CORNER}", 1),
            ("design__instance__area__stdcell", math.nan),
            ("design__instance__area__macros", math.nan),
            ("power__total", math.inf),
            ("power__total", 0.0),
        ):
            mutant = dict(baseline)
            mutant[field] = value
            metrics_path.write_text(json.dumps(mutant))
            assert parse_result(root, "a" * 64, 8, True)["eligible"] is False, field
        metrics_path.write_text(json.dumps(baseline))
        assert parse_result(root, "a" * 64, 8, False)["eligible"] is False
        metrics_path.write_text(json.dumps(baseline))
        (root / "runs/candidate/final/odb/lnp64_soc.odb").unlink()
        assert parse_result(root, "a" * 64, 8, True)["eligible"] is False
    print("GF180 result parser mutations: PASS")


if __name__ == "__main__":
    main()
