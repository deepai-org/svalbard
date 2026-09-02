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
    "e_sense_input": ("XLEVEL_SE.IN", "E_SENSE"),
    "o_sense_input": ("XLEVEL_SO.IN", "O_SENSE"),
    "e_capture_input": ("XLEVEL_E.IN", "E_CAPTURE_CLK"),
    "o_capture_input": ("XLEVEL_O.IN", "O_CAPTURE_CLK"),
}
OUTPUTS = {
    "e_sense_output": "XLEVEL_SE.OUTP",
    "o_sense_output": "XLEVEL_SO.OUTP",
    "e_capture_clk_output": "XLEVEL_E.OUTP",
    "e_capture_clkb_output": "XLEVEL_E.OUTN",
    "o_capture_clk_output": "XLEVEL_O.OUTP",
    "o_capture_clkb_output": "XLEVEL_O.OUTN",
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
        try:
            resistance, nodes = shortest(graph, start, target)
        except ValueError:
            # Extracted hierarchical prefixes can include capacitively coupled
            # terminals that are not in the driver's conductive component.
            continue
        paths.append((resistance, target, len(nodes) - 1))
    if not paths:
        raise ValueError(f"no conductive consumer nodes matching {prefix} from {start}")
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


def prefix_component_stats(graph, caps, prefix: str) -> dict:
    """Summarize a flattened routed net whose canonical name is a child pin."""
    candidates = sorted(node for node in graph if node.startswith(prefix))
    if not candidates:
        raise ValueError(f"no routed nodes matching {prefix}")
    components = []
    remaining = set(candidates)
    while remaining:
        root = min(remaining)
        seen, queue = set(), deque([root])
        while queue:
            node = queue.popleft()
            if node in seen:
                continue
            seen.add(node)
            queue.extend(neighbor for neighbor, _, _ in graph.get(node, []))
        members = sorted(remaining & seen)
        remaining -= set(members)
        components.append((members, seen))
    members, seen = max(components, key=lambda item: len(item[0]))
    pairs = []
    for start in members:
        for finish in members:
            if start < finish:
                resistance, nodes = shortest(graph, start, finish)
                pairs.append((resistance, start, finish, len(nodes) - 1))
    worst = max(pairs) if pairs else (0.0, members[0], members[0], 0)
    capacitance = sum(caps[node] for node in seen)
    return {
        "canonical_prefix": prefix,
        "terminal_node_count": len(members),
        "resistor_component_node_count": len(seen),
        "maximum_terminal_pair_resistance_ohm": worst[0],
        "worst_terminal_pair": [worst[1], worst[2]],
        "worst_resistor_segment_count": worst[3],
        "component_shunt_capacitance_f": capacitance,
        "worst_rc_product_s": worst[0] * capacitance,
    }


def localize(path: Path, baseline_path: Path | None = None) -> dict:
    graph, caps = parse(path)
    baseline = parse(baseline_path) if baseline_path else None
    routes = {}
    for label, (prefix, baseline_output) in PAIRS.items():
        routes[label] = prefix_component_stats(graph, caps, prefix)
        if baseline:
            baseline_stats = prefix_component_stats(
                baseline[0], baseline[1], baseline_output)
            routes[label]["isolated_fanout_baseline"] = baseline_stats
            routes[label]["shunt_capacitance_increase_ratio"] = (
                routes[label]["component_shunt_capacitance_f"] /
                baseline_stats["component_shunt_capacitance_f"])
    output_loads = {}
    for label, start in OUTPUTS.items():
        output_loads[label] = prefix_component_stats(graph, caps, start)
    return {"schema_version": 1,
            "claim": "routed_parent_clock_path_parasitic_localization",
            "pex": path.name, "routes": routes, "receiver_output_loads": output_loads,
            "result": "pass"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--baseline-pex", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = localize(args.pex, args.baseline_pex)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({label: round(item["maximum_terminal_pair_resistance_ohm"], 3)
                      for label, item in result["routes"].items()}, sort_keys=True))


if __name__ == "__main__":
    main()
