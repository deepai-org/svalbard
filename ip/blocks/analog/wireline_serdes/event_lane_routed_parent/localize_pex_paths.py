#!/usr/bin/env python3
"""Report routed resistance and shunt capacitance between selected PEX nodes."""

from __future__ import annotations

import argparse
import heapq
import json
import re
from collections import defaultdict, deque
from pathlib import Path


PAIRS = {
    "e_sense": ("XFANOUT.E_SENSE", "XLANE.E_SENSE_CLK."),
    "o_sense": ("XFANOUT.O_SENSE", "XLANE.O_SENSE_CLK."),
    "e_capture_clk": ("XFANOUT.E_CAPTURE_CLK", "XLANE.E_CAPTURE_CLK."),
    "o_capture_clk": ("XFANOUT.O_CAPTURE_CLK", "XLANE.O_CAPTURE_CLK."),
    "e_capture_clkb": ("XFANOUT.E_CAPTURE_CLKB", "XLANE.E_CAPTURE_CLKB."),
    "o_capture_clkb": ("XFANOUT.O_CAPTURE_CLKB", "XLANE.O_CAPTURE_CLKB."),
}
NUMBER = re.compile(r"^([-+0-9.eE]+)([fpnumk]?)$")
SCALE = {"": 1.0, "f": 1e-15, "p": 1e-12, "n": 1e-9,
         "u": 1e-6, "m": 1e-3, "k": 1e3}


def numeric(value: str) -> float:
    match = NUMBER.fullmatch(value)
    if not match:
        raise ValueError(f"unsupported numeric value {value}")
    return float(match.group(1)) * SCALE[match.group(2)]


def parse(path: Path):
    graph = defaultdict(list)
    caps = defaultdict(float)
    for raw in path.read_text().splitlines():
        fields = raw.split()
        if len(fields) != 4:
            continue
        name, left, right, value = fields
        if name.startswith("R"):
            resistance = numeric(value)
            graph[left].append((right, resistance, name))
            graph[right].append((left, resistance, name))
        elif name.startswith("C"):
            capacitance = numeric(value)
            if right == "VSS":
                caps[left] += capacitance
            elif left == "VSS":
                caps[right] += capacitance
    return graph, caps


def shortest(graph, start: str, finish: str):
    queue = [(0.0, start, [])]
    best = {}
    while queue:
        total, node, path = heapq.heappop(queue)
        if node in best:
            continue
        best[node] = total
        if node == finish:
            return total, path + [node]
        for neighbor, resistance, _ in graph.get(node, []):
            if neighbor not in best:
                heapq.heappush(queue, (total + resistance, neighbor, path + [node]))
    raise ValueError(f"no resistor path from {start} to {finish}")


def component_capacitance(graph, caps, start: str):
    seen, queue = set(), deque([start])
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        queue.extend(neighbor for neighbor, _, _ in graph.get(node, []))
    return sum(caps[node] for node in seen), len(seen)


def path_stats(graph, caps, start: str, prefix: str) -> dict:
    targets = sorted(node for node in graph if node.startswith(prefix))
    if not targets:
        raise ValueError(f"no consumer nodes matching {prefix}")
    paths = []
    for target in targets:
        resistance, nodes = shortest(graph, start, target)
        paths.append((resistance, target, len(nodes) - 1))
    paths.sort()
    capacitance, node_count = component_capacitance(graph, caps, start)
    worst = paths[-1]
    return {"driver_node": start, "consumer_prefix": prefix,
            "consumer_node_count": len(paths),
            "minimum_series_resistance_ohm": paths[0][0],
            "maximum_series_resistance_ohm": worst[0],
            "worst_consumer_node": worst[1],
            "worst_resistor_segment_count": worst[2],
            "resistor_component_node_count": node_count,
            "component_shunt_capacitance_f": capacitance,
            "worst_rc_product_s": worst[0] * capacitance}


def localize(path: Path, baseline_path: Path | None = None) -> dict:
    graph, caps = parse(path)
    baseline = parse(baseline_path) if baseline_path else None
    routes = {}
    for label, (start, prefix) in PAIRS.items():
        routes[label] = path_stats(graph, caps, start, prefix)
        if baseline:
            output = start.removeprefix("XFANOUT.")
            baseline_stats = path_stats(baseline[0], baseline[1], output, output + ".")
            routes[label]["isolated_fanout_baseline"] = baseline_stats
            routes[label]["shunt_capacitance_increase_ratio"] = (
                routes[label]["component_shunt_capacitance_f"] /
                baseline_stats["component_shunt_capacitance_f"])
    return {"schema_version": 1,
            "claim": "routed_parent_clock_path_parasitic_localization",
            "pex": path.name, "routes": routes,
            "result": "pass"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--baseline-pex", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = localize(args.pex, args.baseline_pex)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({label: round(item["maximum_series_resistance_ohm"], 3)
                      for label, item in result["routes"].items()}, sort_keys=True))


if __name__ == "__main__":
    main()
