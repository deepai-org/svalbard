#!/usr/bin/env python3
"""Generate the flat Magic source for the calibrated CMOS pulse macro."""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass, field
from pathlib import Path


SCALE = {"t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3,
         "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}
LANE_COUNT = 4
PHASE_Y_SHIFT = 160.0


@dataclass
class Subckt:
    ports: list[str]
    defaults: dict[str, str]
    lines: list[list[str]] = field(default_factory=list)


@dataclass
class Device:
    name: str
    group: str
    phase: str
    kind: str
    nodes: tuple[str, str, str, str]
    width_um: float
    mult: int
    lane: int = 0
    cx: float = 0.0
    cy: float = 0.0


@dataclass
class Group:
    name: str
    primitive: str
    phase: str
    ports: dict[str, str]
    devices: list[Device] = field(default_factory=list)


def joined_lines(path: Path) -> list[str]:
    answer: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        if line.startswith("+") and answer:
            answer[-1] += " " + line[1:].strip()
        else:
            answer.append(line)
    return answer


def assignments(tokens: list[str]) -> dict[str, str]:
    result = {}
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            result[key.upper()] = value
    return result


def parse(path: Path) -> dict[str, Subckt]:
    subckts: dict[str, Subckt] = {}
    active: Subckt | None = None
    for line in joined_lines(path):
        tokens = line.split()
        head = tokens[0].lower()
        if head == ".subckt":
            split = next((i for i, t in enumerate(tokens) if t.lower() == "params:"),
                         len(tokens))
            active = Subckt(tokens[2:split], assignments(tokens[split + 1:]))
            subckts[tokens[1]] = active
        elif head == ".ends":
            active = None
        elif active is not None and head.startswith("x"):
            active.lines.append(tokens)
    return subckts


def number(text: str, params: dict[str, str]) -> float:
    value = text.strip("{}")
    seen = set()
    while value.upper() in params and value.upper() not in seen:
        seen.add(value.upper())
        value = params[value.upper()].strip("{}")
    match = re.fullmatch(r"([-+0-9.eE]+)(meg|[tgkmunpf])?", value.lower())
    if not match:
        raise ValueError(f"unsupported numeric expression: {text}")
    return float(match.group(1)) * SCALE.get(match.group(2) or "", 1.0)


def safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", text)


def flatten(subckts: dict[str, Subckt], top: str) -> tuple[list[Device], dict[str, Group]]:
    devices: list[Device] = []
    groups: dict[str, Group] = {}

    def descend(name: str, netmap: dict[str, str], params: dict[str, str], path: str) -> None:
        subckt = subckts[name]
        local_params = dict(subckt.defaults)
        local_params.update(params)

        def net(local: str) -> str:
            if local in netmap:
                return netmap[local]
            return f"{path}__{safe(local)}"

        direct_mos = all(any(model in line for model in ("nfet_03v3", "pfet_03v3"))
                         for line in subckt.lines)
        if direct_mos:
            phase = "E" if path.startswith("XE") else "O"
            groups[path] = Group(path, name, phase,
                                 {port: netmap[port] for port in subckt.ports})
        for tokens in subckt.lines:
            model_index = next((i for i, token in enumerate(tokens)
                                if token in ("nfet_03v3", "pfet_03v3")), None)
            if model_index is not None:
                node_names = tuple(net(token) for token in tokens[1:5])
                values = assignments(tokens[model_index + 1:])
                phase = "E" if path.startswith("XE") else "O"
                device = Device(
                    safe(path + "__" + tokens[0]), path, phase,
                    tokens[model_index], node_names,
                    number(values.get("W", "1u"), local_params) / 1e-6,
                    max(1, round(number(values.get("M", "1"), local_params))),
                )
                devices.append(device)
                groups[path].devices.append(device)
                continue
            child_index = next(i for i, token in enumerate(tokens) if token in subckts)
            child_name = tokens[child_index]
            child = subckts[child_name]
            actual = tokens[1:child_index]
            child_map = {port: net(value) for port, value in zip(child.ports, actual)}
            child_params = dict(local_params)
            # Resolve forwarded parameters in the parent's scope before the
            # child's identically named default shadows them.  For example,
            # cp_delay_unit passes WP={WP} to cp_inv; retaining the literal
            # expression here creates a self-reference during flattening.
            forwarded = assignments(tokens[child_index + 1:])
            for key, value in forwarded.items():
                reference = value.strip("{}").upper()
                child_params[key] = local_params.get(reference, value)
            descend(child_name, child_map, child_params,
                    safe(path + "__" + tokens[0]) if path else safe(tokens[0]))

    topckt = subckts[top]
    descend(top, {port: port for port in topckt.ports}, {}, "")
    return devices, groups


def group_depths(groups: dict[str, Group], phase: str) -> dict[str, int]:
    inputs = {"cp_inv": ("A",), "cp_nand2": ("A", "B"),
              "cp_nor2": ("A", "B"), "cp_tg": ("A", "EN", "ENB"),
              "cp_cond_npd": ("G", "EN"), "cp_gate_cap": ("A",)}
    inputs["cp_tristate_inv"] = ("A", "EN", "ENB")
    outputs = {"cp_inv": "Y", "cp_nand2": "Y", "cp_nor2": "Y",
               "cp_tg": "Y", "cp_cond_npd": "D",
               "cp_gate_cap": None}
    outputs["cp_tristate_inv"] = "Y"
    local = [group for group in groups.values() if group.phase == phase]
    clock = "CLKP" if phase == "E" else "CLKN"
    net_depth = {clock: 0, "SEL0": 0, "SEL1": 0, "SEL2": 0, "SEL3": 0,
                 "VDD": 0, "VSS": 0}
    depths = {group.name: 1 for group in local}
    for _ in range(128):
        changed = False
        for group in local:
            needed = [group.ports[port] for port in inputs[group.primitive]
                      if group.ports[port] not in ("VDD", "VSS")]
            depth = 1 + max((net_depth.get(net, 0) for net in needed), default=0)
            if depth != depths[group.name]:
                depths[group.name] = depth
                changed = True
            output_port = outputs[group.primitive]
            if output_port is not None:
                output = group.ports[output_port]
                if depth > net_depth.get(output, -1):
                    net_depth[output] = depth
                    changed = True
        if not changed:
            break
    return depths


def device_span(device: Device) -> float:
    return 0.8 * device.mult + 0.36


def gate_extra(device: Device) -> float:
    """Return extra poly-contact clearance below narrow device diffusion."""
    # The deliberately minimum-size P11 trim capacitor has only 0.3 um of
    # diffusion width.  Move its gate contact far enough below the source
    # access that the two different-net metal2 straps retain spacing; the
    # generic narrow-device clearance leaves their enclosures overlapping.
    if "__XP11L__" in device.name:
        return 0.85
    if ("__XBA__" in device.name or "__XNA__" in device.name) \
            and device.name.endswith("XN0"):
        return 0.75
    return 0.45 if device.width_um < 2.0 else 0.0


def device_column(device: Device) -> int:
    match = re.search(r"__(?:XP|XN)(\d*)$", device.name)
    if not match:
        raise ValueError(f"cannot assign primitive column: {device.name}")
    return int(match.group(1) or 0)


def group_geometry(group: Group) -> tuple[float, dict[str, float]]:
    """Align complementary devices vertically, as a real static-CMOS cell."""
    columns: dict[int, list[Device]] = {}
    for device in group.devices:
        columns.setdefault(device_column(device), []).append(device)
    cursor = 1.5
    offsets_by_name: dict[str, float] = {}
    ordered_columns = sorted(columns)
    for column_index, column in enumerate(ordered_columns):
        span = max(device_span(device) for device in columns[column])
        center = cursor + span / 2.0
        for device in columns[column]:
            offsets_by_name[device.name] = center
        cursor += span
        if column_index + 1 < len(ordered_columns):
            cursor += 6.0
    return cursor + 1.5, offsets_by_name


def functional_lane(group: Group) -> int:
    root = group.name.removeprefix("XE").removeprefix("XO").split("__")[1]
    if root in ("XP08", "XP10", "XP11", "XP11L", "XPMD"):
        return 3
    if root.startswith("XW"):
        return 3
    if root.startswith(("XSM", "XST", "XSN", "XSB", "XRB", "XRBI",
                        "XCM", "XCT", "XPC")):
        return 2
    if root.startswith("XP") or root.startswith("XI"):
        return 1
    if root.startswith("XD"):
        return 0
    return 2


def place(devices: list[Device], groups: dict[str, Group]) -> tuple[float, dict[str, float]]:
    even_depth = group_depths(groups, "E")
    even = [group for group in groups.values() if group.phase == "E"]
    cluster_depth = {}
    for prefix in ("XCM", "XSM", "XWM", "XWE"):
        selected = [group for group in even
                    if re.fullmatch(prefix + r"[0-3]", group.name.split("__")[1])]
        target = max((even_depth[group.name] for group in selected), default=0)
        cluster_depth.update({group.name: target for group in selected})
    place_depth = {group.name: cluster_depth.get(group.name, even_depth[group.name])
                   for group in even}
    ordered = sorted(even, key=lambda group: (place_depth[group.name], group.name))
    group_x: dict[str, float] = {}
    lane_ends = []
    for lane in range(LANE_COUNT):
        cursor = 200.0 if lane == 3 else 12.0
        selected = [group for group in ordered if functional_lane(group) == lane]
        if lane == 1:
            # Keep each write-tap prebuffer beside the mux input it drives.
            # Depth-ordering put the late-tap buffers at the left edge and made
            # P06/P09/P11 travel 80--160 um to the end-selector bank.  The
            # order below follows the physical start/end mux positions; P08,
            # which serves both banks, sits between them.
            # P08 drives two selector gates and was the limiting extracted
            # node.  Put its output between those consumers; P09 has only one
            # local consumer and can tolerate the preceding slot.
            write_taps = ("XP05", "XP09", "XP07")
            write_rank = {name: rank for rank, name in enumerate(write_taps)}

            def lane_one_order(group: Group) -> tuple[int, int, int, str]:
                parts = group.name.split("__")
                root = parts[1]
                stage = int(parts[2].removeprefix("XI")) if len(parts) > 2 else 0
                if root in write_rank:
                    return (1, write_rank[root], stage, group.name)
                return (0, place_depth[group.name], 0, group.name)

            selected.sort(key=lane_one_order)
        if lane == 2:
            # The CT/ST paths form a matched differential timing boundary.
            # Interleave equal restoration stages and put both matched delay
            # elements immediately before the NOR.  Depth/name ordering used
            # to leave CTD roughly 50 um farther from XSN than STD.
            sense_rank = {
                "XPC": 0, "XCM0": 1, "XCM1": 2,
                "XSM0": 3, "XSM1": 4,
                "XCT": 5, "XST": 6,
                "XCTD": 7, "XSTD": 8, "XSN": 9,
                "XSB0": 10, "XRB0": 11, "XRBI": 12,
                "XSB1": 13, "XRB1": 14, "XRBB": 15,
                "XSB2": 16, "XRB2": 17,
            }

            def sense_order(group: Group) -> tuple[int, int, int, str]:
                parts = group.name.split("__")
                root = parts[1]
                stage = int(parts[2].removeprefix("XI")) \
                    if len(parts) > 2 and parts[2].startswith("XI") else 0
                # Interleave corresponding XCT/XST stages rather than placing
                # each complete taper as a separate physical island.
                if root in ("XCT", "XST"):
                    return (5, 2 * stage + int(root == "XST"), 0, group.name)
                return (sense_rank.get(root, 18), 0, place_depth[group.name],
                        group.name)

            selected.sort(key=sense_order)
        if lane == 3:
            # Interleave the active restoring start/end selector cells.  Keep
            # the local P08-to-P09W delay directly between the mid-profile
            # cells, then place the matched restoration stages together.
            selector_rank = {"XWM1": 4, "XWM3": 5, "XPMD": 7,
                             "XWE1": 9, "XP11L": 12, "XWE3": 13}

            def write_order(group: Group) -> tuple[int, int, int, str]:
                parts = group.name.split("__")
                root = parts[1]
                if root in ("XP08", "XP10", "XP11"):
                    stage = int(parts[2].removeprefix("XI"))
                    base = {"XP08": 0, "XP10": 2, "XP11": 10}[root]
                    return (0, base + stage, 0, group.name)
                if root in selector_rank:
                    return (0, selector_rank[root], 0, group.name)
                if root in ("XWST", "XWET"):
                    stage = (int(parts[2].removeprefix("XI"))
                             if parts[2].startswith("XI") else 1.5)
                    if stage == 1:
                        # Terminate each critical selector output locally:
                        # WST immediately after XWM3, WET after XWE3.
                        return (0, 6 + 8 * int(root == "XWET"), 0,
                                group.name)
                    return (1, 2 * stage + int(root == "XWET"), 0,
                            group.name)
                return (2, place_depth[group.name], 0, group.name)

            selected.sort(key=write_order)
        for group in selected:
            root = group.name.split("__")[1]
            if lane == 1 and root in write_rank:
                cursor = max(cursor, 177.0)
            x = cursor
            width, offsets_by_name = group_geometry(group)
            group_x[group.name] = x
            odd_name = "XO" + group.name.removeprefix("XE")
            group_x[odd_name] = x
            for phase_name in (group.name, odd_name):
                for device in groups[phase_name].devices:
                    device.lane = lane
                    even_name = ("XE" + device.name.removeprefix("XO")
                                 if device.name.startswith("XO") else device.name)
                    device.cx = x + offsets_by_name[even_name]
                    base = 32.0 * lane
                    if group.primitive == "cp_cond_npd":
                        device.cy = base + (-5.0 if device.name.endswith("XN0")
                                            else 3.0)
                    else:
                        device.cy = base + (12.0 if device.kind.startswith("pfet")
                                            else 0.0)
            # The logic/mux lanes are dominated by local RC, so use a compact
            # standard-cell-like channel.  Delay/prebuffer lanes retain the
            # wider channel needed by their many cross-lane tap routes.
            gap = 4.0 if lane >= 2 else 8.0
            cursor = x + width + gap
        lane_ends.append(cursor)
    phase_width = max(lane_ends) + 10.0
    for device in devices:
        if device.phase == "O":
            device.cy += PHASE_Y_SHIFT
    return phase_width, group_x


def tcl_header() -> str:
    return r'''# SPDX-License-Identifier: Apache-2.0
proc rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc via_at {layer x y} {
    rect $layer [expr {$x-0.18}] [expr {$y-0.18}] [expr {$x+0.18}] [expr {$y+0.18}]
}
proc stack23 {x y} {
    rect metal2 [expr {$x-0.28}] [expr {$y-0.28}] [expr {$x+0.28}] [expr {$y+0.28}]
    rect metal3 [expr {$x-0.28}] [expr {$y-0.28}] [expr {$x+0.28}] [expr {$y+0.28}]
    via_at via2 $x $y
}
proc stack34 {x y} {
    rect metal3 [expr {$x-0.28}] [expr {$y-0.28}] [expr {$x+0.28}] [expr {$y+0.28}]
    rect metal4 [expr {$x-0.28}] [expr {$y-0.28}] [expr {$x+0.28}] [expr {$y+0.28}]
    via_at via3 $x $y
}
proc stack45 {x y} {
    rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    via_at via4 $x $y
}
proc full_stack {x y highest} {
    rect metal1 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    rect metal2 [expr {$x-0.28}] [expr {$y-0.28}] [expr {$x+0.28}] [expr {$y+0.28}]
    via_at via1 $x $y
    if {$highest >= 3} { stack23 $x $y }
    if {$highest >= 4} { stack34 $x $y }
    if {$highest >= 5} { stack45 $x $y }
}
proc pcontact {x y} {
    rect psubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] [expr {$x+0.25}] [expr {$y+0.30}]
}
proc ncontact {x y} {
    rect nsubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] [expr {$x+0.25}] [expr {$y+0.30}]
}
proc diff_offsets {nf parity} {
    set answer {}
    set index 0
    for {set x [expr {-0.4*$nf}]} {$index <= $nf} {set x [expr {$x+0.8}]; incr index} {
        if {$index % 2 == $parity} { lappend answer $x }
    }
    return $answer
}
proc gate_offsets {nf} {
    set answer {}
    for {set index 0} {$index < $nf} {incr index} {
        lappend answer [expr {-0.4*($nf-1)+0.8*$index}]
    }
    return $answer
}
proc draw_mos {kind width nf cx cy} {
    set diffusion [expr {[string match "pfet*" $kind] ? "pdiff" : "ndiff"}]
    set contact [expr {[string match "pfet*" $kind] ? "pdc" : "ndc"}]
    set xs [lsort -real [concat [diff_offsets $nf 0] [diff_offsets $nf 1]]]
    set left [expr {$cx+[lindex $xs 0]}]
    set right [expr {$cx+[lindex $xs end]}]
    rect $diffusion [expr {$left-0.18}] [expr {$cy-$width/2.0}] [expr {$right+0.18}] [expr {$cy+$width/2.0}]
    foreach xoff [gate_offsets $nf] {
        set x [expr {$cx+$xoff}]
        rect polysilicon [expr {$x-0.14}] [expr {$cy-$width/2.0-0.22}] [expr {$x+0.14}] [expr {$cy+$width/2.0+0.22}]
    }
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        rect $contact [expr {$x-0.115}] [expr {$cy-$width/2.0+0.065}] [expr {$x+0.115}] [expr {$cy+$width/2.0-0.065}]
        rect metal1 [expr {$x-0.18}] [expr {$cy-$width/2.0}] [expr {$x+0.18}] [expr {$cy+$width/2.0}]
    }
}
proc manual_gate {cx cy width nf extra} {
    set y [expr {$cy-$width/2.0-0.70-$extra}]
    set xs [gate_offsets $nf]
    set half [expr {$nf == 1 ? 0.22 : 0.4*$nf-0.25}]
    rect polysilicon [expr {$cx-$half}] [expr {$y+0.35}] [expr {$cx+$half}] [expr {$y+0.60+$extra}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        rect polysilicon [expr {$x-0.20}] [expr {$y-0.30}] [expr {$x+0.20}] [expr {$y+0.60+$extra}]
        rect polycontact [expr {$x-0.115}] [expr {$y-0.215}] [expr {$x+0.115}] [expr {$y+0.015}]
    }
    rect metal1 [expr {$cx+[lindex $xs 0]-0.35}] [expr {$y-0.30}] [expr {$cx+[lindex $xs end]+0.35}] [expr {$y+0.30}]
    return $y
}
proc make_port {name number x y} {
    rect metal5 [expr {$x-0.48}] [expr {$y-0.48}] [expr {$x+0.48}] [expr {$y+0.48}]
    box values [expr {$x-0.48}] [expr {$y-0.48}] [expr {$x+0.48}] [expr {$y+0.48}]
    label $name FreeSans 0.5 0 0 0 c metal5
    port make $number
}
crashbackups stop
load clock_pulse_generator
units microns
'''


def route_columns(devices: list[Device], reserved: list[float],
                  tracks: dict[str, float]) -> dict[tuple[str, str], float]:
    occupied: dict[str, list[tuple[float, float, float, str]]] = {
        phase: [] for phase in ("E", "O")}
    metal2_occupied: dict[str, list[tuple[float, float, float, float, str]]] = {
        phase: [] for phase in ("E", "O")}
    for phase in ("E", "O"):
        phase_offset = PHASE_Y_SHIFT if phase == "O" else 0.0
        for x in reserved:
            for lane in range(LANE_COUNT):
                base = 32.0 * lane
                base += phase_offset
                occupied[phase].append(
                    (x, min(base - 6.0, tracks[f"{phase}{lane}:VSS"]) - 0.28,
                     max(base - 6.0, tracks[f"{phase}{lane}:VSS"]) + 0.28,
                     "VSS"))
                occupied[phase].append(
                    (x, min(base + 19.0, tracks[f"{phase}{lane}:VDD"]) - 0.28,
                     max(base + 19.0, tracks[f"{phase}{lane}:VDD"]) + 0.28,
                     "VDD"))
                metal2_occupied[phase].append(
                    (x - 0.28, base - 6.28, x + 0.28, base - 5.72, "VSS"))
                metal2_occupied[phase].append(
                    (x - 0.28, base + 18.72, x + 0.28, base + 19.28, "VDD"))
    answer: dict[tuple[str, str], float] = {}
    for device in devices:
        phase_columns = occupied[device.phase]
        span = device_span(device)
        preferred = {"D": device.cx - span / 2.0 - 0.75,
                     "G": device.cx,
                     "S": device.cx + span / 2.0 + 0.75}
        width = device.width_um
        terminal_y = {
            "D": device.cy + max(0.70, width / 2.0 - 0.8),
            "G": device.cy - width / 2.0 - 0.70 - gate_extra(device),
            "S": device.cy - max(0.70, width / 2.0 - 0.8),
        }
        terminal_points = {
            "D": [device.cx + x for x in offsets(device.mult, 0)],
            "G": [device.cx + x for x in gate_offsets(device.mult)],
            "S": [device.cx + x for x in offsets(device.mult, 1)],
        }
        for terminal, net in zip(("D", "G", "S"), device.nodes[:3]):
            key = (device.name, terminal)
            track_y = tracks[route_key(device, net)]
            low_y = min(terminal_y[terminal], track_y) - 0.28
            high_y = max(terminal_y[terminal], track_y) + 0.28
            for step in range(2000):
                candidates = (preferred[terminal] + 0.1 * step,
                              preferred[terminal] - 0.1 * step)
                chosen = None
                chosen_metal2 = None
                for candidate in candidates:
                    points = terminal_points[terminal]
                    half_metal2 = 0.28 if terminal == "G" else 0.38
                    candidate_metal2 = (
                        min(candidate, points[0]) - half_metal2,
                        terminal_y[terminal] - half_metal2,
                        max(candidate, points[-1]) + half_metal2,
                        terminal_y[terminal] + half_metal2)
                    column_legal = all(
                        abs(candidate - old_x) >= 0.86
                        or high_y + 0.40 <= old_low_y
                        or old_high_y + 0.40 <= low_y
                        for old_x, old_low_y, old_high_y, old_net
                        in phase_columns)
                    metal2_legal = all(
                        old_net == net
                        or candidate_metal2[2] + 0.28 <= old_x1
                        or old_x2 + 0.28 <= candidate_metal2[0]
                        or candidate_metal2[3] + 0.28 <= old_y1
                        or old_y2 + 0.28 <= candidate_metal2[1]
                        for old_x1, old_y1, old_x2, old_y2, old_net
                        in metal2_occupied[device.phase])
                    if column_legal and metal2_legal:
                        chosen = candidate
                        chosen_metal2 = candidate_metal2
                        break
                if chosen is not None:
                    phase_columns.append((chosen, low_y, high_y, net))
                    metal2_occupied[device.phase].append(
                        (*chosen_metal2, net))
                    answer[key] = chosen
                    break
            else:
                candidate = preferred[terminal]
                points = terminal_points[terminal]
                half_metal2 = 0.28 if terminal == "G" else 0.38
                candidate_metal2 = (
                    min(candidate, points[0]) - half_metal2,
                    terminal_y[terminal] - half_metal2,
                    max(candidate, points[-1]) + half_metal2,
                    terminal_y[terminal] + half_metal2)
                column_blockers = [
                    (round(old_x, 3), old_net)
                    for old_x, old_low_y, old_high_y, old_net in phase_columns
                    if old_net != net and abs(candidate - old_x) < 0.86
                    and high_y + 0.40 > old_low_y
                    and old_high_y + 0.40 > low_y][:6]
                metal2_blockers = [old_net for old_x1, old_y1, old_x2,
                                   old_y2, old_net
                                   in metal2_occupied[device.phase]
                                   if old_net != net
                                   and candidate_metal2[2] + 0.28 > old_x1
                                   and old_x2 + 0.28 > candidate_metal2[0]
                                   and candidate_metal2[3] + 0.28 > old_y1
                                   and old_y2 + 0.28 > candidate_metal2[1]][:6]
                raise RuntimeError(
                    f"no access column for {device.name} {terminal}; "
                    f"preferred column blockers={column_blockers}, "
                    f"metal2 blockers={metal2_blockers}")
    return answer


def validate_metal2_access(devices: list[Device],
                           columns: dict[tuple[str, str], float]) -> None:
    """Reject same-layer access overlaps that geometric DRC cannot call shorts."""
    rectangles: list[tuple[float, float, float, float, str, str]] = []
    for device in devices:
        width = device.width_um
        nf = device.mult
        drain_y = device.cy + max(0.70, width / 2.0 - 0.8)
        source_y = device.cy - max(0.70, width / 2.0 - 0.8)
        for terminal, net, y, points in (
                ("D", device.nodes[0], drain_y,
                 [device.cx + x for x in offsets(nf, 0)]),
                ("S", device.nodes[2], source_y,
                 [device.cx + x for x in offsets(nf, 1)])):
            route_x = columns[(device.name, terminal)]
            rectangles.append((min(route_x, points[0]) - 0.38, y - 0.38,
                               max(route_x, points[-1]) + 0.38, y + 0.38,
                               net, f"{device.name}:{terminal}"))
        gate_y = device.cy - width / 2.0 - 0.70 - gate_extra(device)
        route_x = columns[(device.name, "G")]
        gates = [device.cx + x for x in gate_offsets(nf)]
        rectangles.append((min(route_x, gates[0]) - 0.28, gate_y - 0.28,
                           max(route_x, gates[-1]) + 0.28, gate_y + 0.28,
                           device.nodes[1], f"{device.name}:G"))

    for index, first in enumerate(rectangles):
        for second in rectangles[index + 1:]:
            if first[4] == second[4]:
                continue
            overlap_x = min(first[2], second[2]) - max(first[0], second[0])
            overlap_y = min(first[3], second[3]) - max(first[1], second[1])
            if overlap_x > 1e-6 and overlap_y > 1e-6:
                raise RuntimeError(
                    "different-net metal2 access overlap: "
                    f"{first[5]} ({first[4]}) and {second[5]} ({second[4]})")


def route_key(device: Device, net: str) -> str:
    if net in ("VDD", "VSS"):
        return f"{device.phase}{device.lane}:{net}"
    if net in ("SEL0", "SEL1", "SEL2", "SEL3"):
        return f"{device.phase}:{net}"
    return net


def interval_lanes(keys: list[str], bounds: dict[str, list[float]]) -> dict[str, int]:
    lane_ends: list[float] = []
    answer: dict[str, int] = {}
    for key in sorted(keys, key=lambda item: (bounds[item][0], bounds[item][1])):
        start, end = bounds[key]
        lane = next((index for index, old_end in enumerate(lane_ends)
                     if old_end + 1.4 <= start), len(lane_ends))
        if lane == len(lane_ends):
            lane_ends.append(end)
        else:
            lane_ends[lane] = end
        answer[key] = lane
    return answer


def emit(source: Path, output: Path) -> None:
    subckts = parse(source)
    devices, groups = flatten(subckts, "clock_pulse_generator")
    xmax, _ = place(devices, groups)
    tap_xs = list(frange(7.0, xmax - 4.0, 28.0))
    first_seen: dict[str, int] = {}
    key_lane_sets: dict[str, set[int]] = {}
    for device in devices:
        for net in device.nodes[:3]:
            key = route_key(device, net)
            first_seen.setdefault(key, len(first_seen))
            key_lane_sets.setdefault(key, set()).add(device.lane)
    special_tracks = {
        f"{phase}{lane}:{rail}": offset + 32.0 * lane + rail_offset
        for phase, offset in (("E", 0.0), ("O", PHASE_Y_SHIFT))
        for lane in range(LANE_COUNT)
        for rail, rail_offset in (("VSS", -8.0), ("VDD", 21.0))
    }
    # The write-selector outputs switch in opposite directions and are both
    # degraded by an enabled transmission gate.  Keep their long metal4 runs
    # at opposite edges of the lane instead of on adjacent tracks; extraction
    # of the adjacent version showed 5.14 fF of mutual capacitance.
    fixed_signal_tracks = {
        # Avoid 89.5/249.5: those are also the allocator's lane-3 track zero.
        # Reusing that ordinate can create a DRC-clean electrical short when
        # a different local net happens to receive slot zero.
        "XE__WSTART_SEL": 90.5, "XE__WEND_SEL": 114.5,
        "XO__WSTART_SEL": 250.5, "XO__WEND_SEL": 274.5,
    }
    signal_keys = [key for key in first_seen if key not in special_tracks]
    approximate_bounds: dict[str, list[float]] = {
        key: [math.inf, -math.inf]
        for key in set(special_tracks) | set(first_seen)}
    debug_labels = {
        "XE__D08": "DBG_E_D08", "XE__D09": "DBG_E_D09",
        "XE__WSTART_SEL": "DBG_E_WSTART_SEL",
        "XE__WEND_SEL": "DBG_E_WEND_SEL",
        "XE__WST": "DBG_E_WST", "XE__WET": "DBG_E_WET",
        "XE__WCOREB": "DBG_E_WCOREB", "XE__WB0": "DBG_E_WB0",
        "XE__WB1": "DBG_E_WB1", "XE__SSEL": "DBG_E_SSEL",
        "XE__CT": "DBG_E_CT", "XE__ST": "DBG_E_ST",
        "XE__CTD": "DBG_E_CTD", "XE__STD": "DBG_E_STD",
        "XE__SN0": "DBG_E_SN0", "XE__SB0": "DBG_E_SB0",
        "XE__SB1": "DBG_E_SB1",
        "XE__PCLK": "DBG_E_PCLK", "XE__P08": "DBG_E_P08",
        "XE__P09": "DBG_E_P09", "XE__CTSEL": "DBG_E_CTSEL",
        "XE__XCT__B0": "DBG_E_CTB0", "XE__XCT__B1": "DBG_E_CTB1",
        "XE__XCT__B2": "DBG_E_CTB2", "XE__XST__B0": "DBG_E_STB0",
        "XE__XST__B1": "DBG_E_STB1", "XE__XST__B2": "DBG_E_STB2",
        "XE__XWST__B1": "DBG_E_WSTB1",
        "XE__XWST__B2": "DBG_E_WSTB2",
        "XE__XWET__B1": "DBG_E_WETB1", "XE__XWET__B2": "DBG_E_WETB2",
        "XO__P08": "DBG_O_P08", "XO__P09": "DBG_O_P09",
        "XO__WSTART_SEL": "DBG_O_WSTART_SEL",
        "XO__WEND_SEL": "DBG_O_WEND_SEL",
        "XO__WST": "DBG_O_WST", "XO__WET": "DBG_O_WET",
        "XO__XWST__B1": "DBG_O_WSTB1",
        "XO__XWST__B2": "DBG_O_WSTB2",
        "XO__XWET__B1": "DBG_O_WETB1", "XO__XWET__B2": "DBG_O_WETB2",
    }
    for device in devices:
        span = device_span(device) + 2.0
        for net in device.nodes[:3]:
            key = route_key(device, net)
            approximate_bounds[key][0] = min(approximate_bounds[key][0],
                                             device.cx - span)
            approximate_bounds[key][1] = max(approximate_bounds[key][1],
                                             device.cx + span)

    top_ports = subckts["clock_pulse_generator"].ports
    top_keys: dict[str, list[str]] = {}
    for port in top_ports:
        if port in ("VDD", "VSS"):
            top_keys[port] = [f"{phase}{lane}:{port}"
                              for phase in ("E", "O")
                              for lane in range(LANE_COUNT)]
        elif port in ("SEL0", "SEL1", "SEL2", "SEL3"):
            top_keys[port] = [f"E:{port}", f"O:{port}"]
        else:
            top_keys[port] = [port]
    input_ports = [port for port in top_ports if not port.startswith(("E_", "O_"))]
    output_ports = [port for port in top_ports if port.startswith(("E_", "O_"))]
    port_xs = {port: -2.0 - 2.0 * index for index, port in enumerate(input_ports)}
    port_xs.update({port: xmax + 2.0 + 2.0 * index
                    for index, port in enumerate(output_ports)})
    for port, keys in top_keys.items():
        endpoint = port_xs[port]
        for key in keys:
            approximate_bounds[key][0] = min(approximate_bounds[key][0], endpoint)
            approximate_bounds[key][1] = max(approximate_bounds[key][1], endpoint)
    even_keys = [key for key in signal_keys
                 if not (key.startswith("XO") or key.startswith("O:")
                         or key == "CLKN" or key.startswith("O_"))]
    odd_keys = [key for key in signal_keys if key not in even_keys]
    key_groups = {key: min(key_lane_sets[key]) for key in signal_keys}

    def grouped_lanes(keys: list[str], routing_bounds: dict[str, list[float]]):
        answer = {}
        for group in range(LANE_COUNT):
            grouped_keys = [key for key in keys if key_groups[key] == group]
            local = interval_lanes(grouped_keys, routing_bounds)
            answer.update({key: 100 * group + lane for key, lane in local.items()})
        return answer

    def track_y(code: int, odd_phase: bool) -> float:
        group, local_lane = divmod(code, 100)
        if local_lane >= 13:
            raise RuntimeError(f"routing band {group} exceeds 13 tracks per phase")
        return (-6.5 + 32.0 * group + 2.1 * local_lane
                + PHASE_Y_SHIFT * int(odd_phase))

    def assign_tracks(routing_bounds: dict[str, list[float]]):
        even = grouped_lanes(even_keys, routing_bounds)
        odd = grouped_lanes(odd_keys, routing_bounds)
        assigned = dict(special_tracks)
        assigned.update({key: track_y(code, False) for key, code in even.items()})
        assigned.update({key: track_y(code, True) for key, code in odd.items()})
        assigned.update(fixed_signal_tracks)
        return even, odd, assigned

    def exact_bounds(columns: dict[tuple[str, str], float]):
        answer = {key: [math.inf, -math.inf]
                  for key in set(special_tracks) | set(first_seen)}
        for device in devices:
            for terminal, net in zip(("D", "G", "S"), device.nodes[:3]):
                key = route_key(device, net)
                x = columns[(device.name, terminal)]
                answer[key][0] = min(answer[key][0], x)
                answer[key][1] = max(answer[key][1], x)
        for port, keys in top_keys.items():
            endpoint = port_xs[port]
            for key in keys:
                answer[key][0] = min(answer[key][0], endpoint)
                answer[key][1] = max(answer[key][1], endpoint)
        return answer

    even_lanes, odd_lanes, tracks = assign_tracks(approximate_bounds)
    for _ in range(32):
        columns = route_columns(devices, tap_xs, tracks)
        bounds = exact_bounds(columns)
        moved = False
        for phase_lanes in (even_lanes, odd_lanes):
            by_lane: dict[int, list[str]] = {}
            for key, lane in phase_lanes.items():
                by_lane.setdefault(lane, []).append(key)
            move_keys: set[str] = set()
            for keys in by_lane.values():
                ordered_keys = sorted(keys, key=lambda key: bounds[key][0])
                previous = None
                previous_end = -math.inf
                for key in ordered_keys:
                    if previous is not None and previous_end + 1.4 > bounds[key][0]:
                        move_keys.add(key)
                    else:
                        previous = key
                        previous_end = bounds[key][1]
            for key in sorted(move_keys):
                group = phase_lanes[key] // 100
                next_local = 1 + max(
                    (code % 100 for code in phase_lanes.values()
                     if code // 100 == group), default=-1)
                phase_lanes[key] = 100 * group + next_local
                moved = True
        if not moved:
            break
        tracks = dict(special_tracks)
        tracks.update({key: track_y(code, False)
                       for key, code in even_lanes.items()})
        tracks.update({key: track_y(code, True)
                       for key, code in odd_lanes.items()})
        tracks.update(fixed_signal_tracks)
    else:
        raise RuntimeError("exact signal routing did not converge")
    validate_metal2_access(devices, columns)
    lanes = dict(even_lanes)
    lanes.update(odd_lanes)

    lines = [tcl_header()]
    for phase_offset in (0.0, PHASE_Y_SHIFT):
        for lane in range(LANE_COUNT):
            base = 32.0 * lane
            base += phase_offset
            lines.append(f"rect pwell 2 {base-8:.3f} {xmax:.3f} {base+6:.3f}\n")
            lines.append(f"rect nwell 2 {base+7:.3f} {xmax:.3f} {base+20:.3f}\n")
    for device in devices:
        lines.append(f"draw_mos {device.kind} {device.width_um:.6f} {device.mult} "
                     f"{device.cx:.3f} {device.cy:.3f}\n")
    for device in devices:
        width = device.width_um
        nf = device.mult
        d_y = device.cy + max(0.70, width / 2.0 - 0.8)
        s_y = device.cy - max(0.70, width / 2.0 - 0.8)
        d_points = [device.cx + x for x in offsets(nf, 0)]
        s_points = [device.cx + x for x in offsets(nf, 1)]
        gate_y = device.cy - width / 2.0 - 0.70 - gate_extra(device)
        for terminal, net, y, points in (("D", device.nodes[0], d_y, d_points),
                                         ("S", device.nodes[2], s_y, s_points)):
            route_x = columns[(device.name, terminal)]
            for x in points:
                lines.append(f"rect metal1 {x-0.28:.3f} {min(device.cy,y)-0.28:.3f} "
                             f"{x+0.28:.3f} {max(device.cy,y)+0.28:.3f}\n")
                lines.append(f"via_at via1 {x:.3f} {y:.3f}\n")
            lines.append(f"rect metal2 {min(route_x,points[0])-0.38:.3f} {y-0.38:.3f} "
                         f"{max(route_x,points[-1])+0.38:.3f} {y+0.38:.3f}\n")
            lines.append(f"stack23 {route_x:.3f} {y:.3f}\n")
            ty = tracks[route_key(device, net)]
            lines.append(f"rect metal3 {route_x-0.28:.3f} {min(y,ty)-0.28:.3f} "
                         f"{route_x+0.28:.3f} {max(y,ty)+0.28:.3f}\n")
            lines.append(f"stack34 {route_x:.3f} {ty:.3f}\n")
        route_x = columns[(device.name, "G")]
        gates = [device.cx + x for x in gate_offsets(nf)]
        lines.append(f"set _gy [manual_gate {device.cx:.3f} {device.cy:.3f} "
                     f"{width:.6f} {nf} {gate_extra(device):.3f}]\n")
        lines.append(f"full_stack {device.cx:.3f} {gate_y:.3f} 2\n")
        lines.append(f"rect metal2 {min(route_x,gates[0])-0.28:.3f} {gate_y-0.28:.3f} "
                     f"{max(route_x,gates[-1])+0.28:.3f} {gate_y+0.28:.3f}\n")
        lines.append(f"stack23 {route_x:.3f} {gate_y:.3f}\n")
        ty = tracks[route_key(device, device.nodes[1])]
        lines.append(f"rect metal3 {route_x-0.28:.3f} {min(gate_y,ty)-0.28:.3f} "
                     f"{route_x+0.28:.3f} {max(gate_y,ty)+0.28:.3f}\n")
        lines.append(f"stack34 {route_x:.3f} {ty:.3f}\n")

    for key, (x1, x2) in bounds.items():
        y = tracks[key]
        half = 0.38 if key.endswith((":VDD", ":VSS")) else 0.23
        if key in special_tracks:
            x1 = min(x1, tap_xs[0])
            x2 = max(x2, tap_xs[-1])
        lines.append(f"rect metal4 {x1-0.38:.3f} {y-half:.3f} {x2+0.38:.3f} {y+half:.3f}\n")
        if key in debug_labels:
            label_x = (x1 + x2) / 2.0
            lines.append(f"box values {label_x-0.2:.3f} {y-0.2:.3f} "
                         f"{label_x+0.2:.3f} {y+0.2:.3f}\n")
            lines.append(f"label {debug_labels[key]} FreeSans 0.4 0 0 0 c metal4\n")

    for key in special_tracks:
        y = tracks[key]
        lines.append(f"rect metal5 2.000 {y-0.75:.3f} {xmax:.3f} {y+0.75:.3f}\n")
        for x in tap_xs:
            lines.append(f"stack45 {x:.3f} {y:.3f}\n")

    for phase, phase_offset in (("E", 0.0), ("O", PHASE_Y_SHIFT)):
        for lane in range(LANE_COUNT):
            phase_y = 32.0 * lane + phase_offset
            vss_y = tracks[f"{phase}{lane}:VSS"]
            vdd_y = tracks[f"{phase}{lane}:VDD"]
            for x in tap_xs:
                py = phase_y - 6.0
                ny = phase_y + 19.0
                lines.append(f"rect psubdiff {x-0.32:.3f} {py-0.37:.3f} {x+0.32:.3f} {py+0.37:.3f}\n")
                lines.append(f"pcontact {x:.3f} {py:.3f}\nfull_stack {x:.3f} {py:.3f} 3\n")
                lines.append(f"rect metal3 {x-0.28:.3f} {min(py,vss_y)-0.28:.3f} {x+0.28:.3f} {max(py,vss_y)+0.28:.3f}\n")
                lines.append(f"stack34 {x:.3f} {vss_y:.3f}\n")
                lines.append(f"rect nsubdiff {x-0.32:.3f} {ny-0.37:.3f} {x+0.32:.3f} {ny+0.37:.3f}\n")
                lines.append(f"ncontact {x:.3f} {ny:.3f}\nfull_stack {x:.3f} {ny:.3f} 3\n")
                lines.append(f"rect metal3 {x-0.28:.3f} {min(ny,vdd_y)-0.28:.3f} {x+0.28:.3f} {max(ny,vdd_y)+0.28:.3f}\n")
                lines.append(f"stack34 {x:.3f} {vdd_y:.3f}\n")

    for index, port in enumerate(top_ports, 1):
        keys = top_keys[port]
        x = port_xs[port]
        if len(keys) > 1:
            ys = [tracks[key] for key in keys]
            port_y = sum(ys) / len(ys)
            if port in ("VDD", "VSS"):
                lines.append(f"rect metal3 {x-0.75:.3f} {min(ys)-0.38:.3f} {x+0.75:.3f} {max(ys)+0.38:.3f}\n")
                for y in ys:
                    lines.append(f"stack34 {x:.3f} {y:.3f}\n")
                lines.append(f"stack34 {x:.3f} {port_y:.3f}\nstack45 {x:.3f} {port_y:.3f}\n")
            else:
                lines.append(f"rect metal5 {x-0.38:.3f} {min(ys)-0.38:.3f} {x+0.38:.3f} {max(ys)+0.38:.3f}\n")
                for y in ys:
                    lines.append(f"stack45 {x:.3f} {y:.3f}\n")
        else:
            port_y = tracks[keys[0]]
            lines.append(f"stack45 {x:.3f} {port_y:.3f}\n")
        lines.append(f"make_port {port} {index} {x:.3f} {port_y:.3f}\n")

    lines.append("save /work/clock_pulse_generator\n")
    lines.append("gds write /work/clock_pulse_generator.gds\n")
    lines.append("quit -noprompt\n")
    output.write_text("".join(lines))
    even_track_count = max((code % 100 for code in even_lanes.values()), default=-1) + 1
    odd_track_count = max((code % 100 for code in odd_lanes.values()), default=-1) + 1
    print(f"groups={len(groups)} devices={len(devices)} width_um={xmax:.1f} "
          f"nets={len(tracks)} lanes={even_track_count}/{odd_track_count}")


def offsets(nf: int, parity: int) -> list[float]:
    return [-0.4 * nf + 0.8 * index for index in range(nf + 1)
            if index % 2 == parity]


def gate_offsets(nf: int) -> list[float]:
    return [-0.4 * (nf - 1) + 0.8 * index for index in range(nf)]


def frange(start: float, stop: float, step: float):
    value = start
    while value <= stop:
        yield value
        value += step


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    emit(args.source, args.output)


if __name__ == "__main__":
    main()
