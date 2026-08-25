#!/usr/bin/env python3
"""Summarize resistance and capacitance on named Magic PEX nets."""

from __future__ import annotations

import argparse
import heapq
import json
import math
import re
from collections import defaultdict
from pathlib import Path


SCALE = {
    "t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3,
    "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15,
}
VALUE = re.compile(r"([-+0-9.eE]+)(meg|[tgkmunpf])?", re.IGNORECASE)
PEX_SUFFIX = re.compile(r"\.(?:n|t)\d+$")


def number(text: str) -> float:
    match = VALUE.fullmatch(text)
    if not match:
        raise ValueError(f"unsupported SPICE value: {text}")
    return float(match.group(1)) * SCALE.get((match.group(2) or "").lower(), 1.0)


def logical(node: str) -> str:
    return PEX_SUFFIX.sub("", node)


def joined_lines(path: Path):
    pending = ""
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        if line.startswith("+"):
            pending += " " + line[1:].strip()
            continue
        if pending:
            yield pending
        pending = line
    if pending:
        yield pending


def parse(path: Path):
    resistors = []
    capacitors = []
    device_nodes = set()
    devices = []
    for line in joined_lines(path):
        fields = line.split()
        kind = fields[0][0].lower()
        if kind == "r" and len(fields) >= 4:
            resistors.append((fields[1], fields[2], number(fields[3])))
        elif kind == "c" and len(fields) >= 4:
            capacitors.append((fields[1], fields[2], number(fields[3])))
        elif kind in ("m", "x") and len(fields) >= 5:
            device_nodes.update(fields[1:5])
            devices.append({
                "name": fields[0],
                "nodes": fields[1:5],
                "model": fields[5] if len(fields) >= 6 else "",
            })
    return resistors, capacitors, device_nodes, devices


def distances(root: str, edges):
    graph = defaultdict(list)
    for left, right, resistance in edges:
        graph[left].append((right, resistance))
        graph[right].append((left, resistance))
    distance = {root: 0.0}
    queue = [(0.0, root)]
    while queue:
        value, node = heapq.heappop(queue)
        if value != distance[node]:
            continue
        for neighbor, resistance in graph[node]:
            candidate = value + resistance
            if candidate < distance.get(neighbor, math.inf):
                distance[neighbor] = candidate
                heapq.heappush(queue, (candidate, neighbor))
    return distance


def resistance_paths(root: str, targets: set[str], edges):
    """Return shortest metal resistance and the worst reachable terminal path."""
    graph = defaultdict(list)
    for left, right, resistance in edges:
        graph[left].append((right, resistance))
        graph[right].append((left, resistance))
    distance = {root: 0.0}
    previous = {}
    queue = [(0.0, root)]
    while queue:
        value, node = heapq.heappop(queue)
        if value != distance[node]:
            continue
        for neighbor, resistance in graph[node]:
            candidate = value + resistance
            if candidate < distance.get(neighbor, math.inf):
                distance[neighbor] = candidate
                previous[neighbor] = (node, resistance)
                heapq.heappush(queue, (candidate, neighbor))
    reachable = sorted((distance[node], node) for node in targets if node in distance)
    if not reachable:
        return {
            "target_count": len(targets),
            "reachable_target_count": 0,
            "minimum_ohm": math.inf,
            "median_ohm": math.inf,
            "maximum_ohm": math.inf,
            "worst_target": None,
            "worst_path": [],
        }
    worst_value, worst_node = reachable[-1]
    path = []
    cursor = worst_node
    while cursor != root:
        parent, resistance = previous[cursor]
        path.append({"from": parent, "to": cursor, "resistance_ohm": resistance})
        cursor = parent
    path.reverse()
    return {
        "target_count": len(targets),
        "reachable_target_count": len(reachable),
        "minimum_ohm": reachable[0][0],
        "median_ohm": reachable[len(reachable) // 2][0],
        "maximum_ohm": worst_value,
        "worst_target": worst_node,
        "worst_path": path,
    }


def device_path_report(root: str, gate_pattern: str, model_pattern: str,
                       terminal: str, resistors, devices):
    index = {"drain": 0, "gate": 1, "source": 2, "body": 3}[terminal]
    gate_re = re.compile(gate_pattern)
    model_re = re.compile(model_pattern)
    selected = [device for device in devices
                if gate_re.search(device["nodes"][1])
                and model_re.search(device["model"])]
    targets = {device["nodes"][index] for device in selected
               if logical(device["nodes"][index]) == root}
    edges = [item for item in resistors
             if logical(item[0]) == root and logical(item[1]) == root]
    result = resistance_paths(root, targets, edges)
    result.update({
        "root": root,
        "gate_pattern": gate_pattern,
        "model_pattern": model_pattern,
        "terminal": terminal,
        "selected_device_count": len(selected),
        "selected_terminal_count_on_root": len(targets),
    })
    return result


def report(net: str, resistors, capacitors, device_nodes):
    edges = [item for item in resistors
             if logical(item[0]) == net and logical(item[1]) == net]
    nodes = {node for edge in edges for node in edge[:2]}
    terminals = sorted(node for node in nodes | device_nodes
                       if logical(node) == net and re.search(r"\.t\d+$", node))
    distance = distances(net, edges)
    reachable = [distance[node] for node in terminals if node in distance]
    ground_cap = 0.0
    internal_cap = 0.0
    coupling = defaultdict(float)
    for left, right, capacitance in capacitors:
        left_net, right_net = logical(left), logical(right)
        if left_net == net and right_net == net:
            internal_cap += capacitance
        elif left_net == net or right_net == net:
            other = right_net if left_net == net else left_net
            if other in ("0", "VSS"):
                ground_cap += capacitance
            else:
                coupling[other] += capacitance
    total_coupling = sum(coupling.values())
    return {
        "net": net,
        "resistor_count": len(edges),
        "resistance_sum_ohm": sum(edge[2] for edge in edges),
        "resistance_max_edge_ohm": max((edge[2] for edge in edges), default=0.0),
        "resistance_max_root_to_terminal_ohm": max(reachable, default=math.inf),
        "terminal_count": len(terminals),
        "unreachable_terminal_count": len(terminals) - len(reachable),
        "ground_cap_f": ground_cap,
        "internal_cap_f": internal_cap,
        "coupling_cap_f": total_coupling,
        "top_coupling": sorted(coupling.items(), key=lambda item: -item[1])[:5],
    }


def fmt_resistance(value: float) -> str:
    return "unreachable" if math.isinf(value) else f"{value:.3f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pex", type=Path)
    parser.add_argument("nets", nargs="*")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root")
    parser.add_argument("--device-gate-regex")
    parser.add_argument("--device-model-regex", default=".*")
    parser.add_argument("--terminal", choices=("drain", "gate", "source", "body"),
                        default="source")
    args = parser.parse_args()
    if not args.nets and not (args.root and args.device_gate_regex):
        parser.error("provide at least one net or --root with --device-gate-regex")
    resistors, capacitors, device_nodes, devices = parse(args.pex)
    results = [report(net, resistors, capacitors, device_nodes) for net in args.nets]
    path_result = None
    if args.root and args.device_gate_regex:
        path_result = device_path_report(
            args.root, args.device_gate_regex, args.device_model_regex,
            args.terminal, resistors, devices)
    if args.json:
        output = {"pex": str(args.pex), "nets": results}
        if path_result is not None:
            output["device_path"] = path_result
        print(json.dumps(output, indent=2))
        return
    print("net R# Rsum_ohm Rmax_ohm Rroot_max_ohm terminals missing Cgnd_fF Ccpl_fF top_coupling")
    for item in results:
        partners = ",".join(f"{name}:{value * 1e15:.2f}"
                            for name, value in item["top_coupling"])
        print(
            f'{item["net"]} {item["resistor_count"]} '
            f'{item["resistance_sum_ohm"]:.3f} '
            f'{item["resistance_max_edge_ohm"]:.3f} '
            f'{fmt_resistance(item["resistance_max_root_to_terminal_ohm"])} '
            f'{item["terminal_count"]} {item["unreachable_terminal_count"]} '
            f'{item["ground_cap_f"] * 1e15:.3f} '
            f'{item["coupling_cap_f"] * 1e15:.3f} {partners}'
        )
    if path_result is not None:
        print(
            "device_path "
            f'root={path_result["root"]} terminal={path_result["terminal"]} '
            f'devices={path_result["selected_device_count"]} '
            f'targets={path_result["selected_terminal_count_on_root"]} '
            f'reachable={path_result["reachable_target_count"]} '
            f'Rmin={fmt_resistance(path_result["minimum_ohm"])} '
            f'Rmedian={fmt_resistance(path_result["median_ohm"])} '
            f'Rmax={fmt_resistance(path_result["maximum_ohm"])}'
        )
        for edge in path_result["worst_path"]:
            print(f'  {edge["from"]} -> {edge["to"]} '
                  f'{edge["resistance_ohm"]:.3f} ohm')


if __name__ == "__main__":
    main()
