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
LANE_PITCH = 36.0
PHASE_Y_SHIFT = 176.0


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

        # A physical primitive may combine direct MOS devices with a child
        # helper (for example a base inverter plus a conditional series
        # branch). Keep its direct devices in one group and descend into the
        # child normally; the old all-or-nothing test lost the parent group.
        direct_mos = any(any(model in line
                             for model in ("nfet_03v3", "pfet_03v3"))
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
    inputs = {"cp_inv": ("A",), "cp_final_inv": ("A",),
              "cp_sense_final_inv": ("A",),
              "cp_nand2": ("A", "B"),
              "cp_nor2": ("A", "B"), "cp_tg": ("A", "EN", "ENB"),
              "cp_cond_npd": ("G", "EN"),
              "cp_gate_cap": ("A",), "cp_route_anchor": ("A",),
              "cp_profile3_delay": ("A",),
              "cp_sense_tail_delay": ("A",),
              "cp_profile_write_restore": ("A", "FAST")}
    inputs.update({
        "cp_nand2_comp": ("A", "B"),
        "cp_cond_npd_comp": ("G", "EN"),
        "cp_sense_final_select": ("A", "EN"),
        "cp_fall_window": ("A", "B"),
    })
    inputs["cp_tristate_inv"] = ("A", "EN", "ENB")
    outputs = {"cp_inv": "Y", "cp_final_inv": "Y",
               "cp_sense_final_inv": "Y",
               "cp_nand2": "Y", "cp_nor2": "Y",
               "cp_tg": "Y", "cp_cond_npd": "D",
               "cp_gate_cap": None, "cp_route_anchor": None,
               "cp_profile3_delay": "Y",
               "cp_sense_tail_delay": "Y",
               "cp_profile_write_restore": "Y"}
    outputs.update({
        "cp_nand2_comp": "Y",
        "cp_cond_npd_comp": "D",
        "cp_sense_final_select": "Y",
        "cp_fall_window": "Y",
    })
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
    # Keep the selected base transmission-gate PMOS clear of the long SEL1
    # access rectangle. A compact neighboring lane can change legal tap
    # columns enough to expose this overlap; moving the contact along the same
    # poly is topology preserving. The observed collision requires 0.84 um.
    if "__XWRITE__XBTG1__XP" in device.name:
        return 1.0
    # The deliberately minimum-size P11 trim capacitor has only 0.3 um of
    # diffusion width.  Move its gate contact far enough below the source
    # access that the two different-net metal2 straps retain spacing; the
    # generic narrow-device clearance leaves their enclosures overlapping.
    if "__XP11L__" in device.name:
        return 0.85
    if ("__XBA__" in device.name or "__XNA__" in device.name) \
            and device.name.endswith("XN0"):
        return 0.75
    # Keep the first middle-profile PMOS gate strap below the nearby SEL3
    # access rectangle when later sense groups deepen the placement graph.
    # The contact remains on the same poly gate; only its Metal2 landing moves.
    if "__XWMCB__" in device.name \
            and device.name.endswith(("XP0", "XN0")):
        return 2.0
    # Keep the SENSE receiver gate landing clear of the same device's supply
    # landing. Moving only the contact along existing poly preserves the
    # electrical input load.
    if re.search(r"__XWISO[0-3]__", device.name):
        return 1.0
    if re.search(r"__XA(?:CLK|SEL[0-3]|Q2)__", device.name):
        return 1.0
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


def instance_path(name: str) -> list[str]:
    """Return functional instance tokens below phase and optional wrappers."""
    parts = name.split("__")[1:]
    if parts and parts[0] == "XWRITE":
        parts = parts[1:]
    return parts


def instance_root(name: str) -> str:
    parts = instance_path(name)
    if not parts:
        raise ValueError(f"cannot find functional instance root: {name}")
    return parts[0]


def functional_lane(group: Group) -> int:
    raw_path = group.name.split("__")[1:]
    # The selected dual-phase parent wraps the complete timing macro in
    # XWRITE. Keep that local state machine in the write lane while still
    # exposing its child identity to ordering and current-routing rules.
    if raw_path and raw_path[0] == "XWRITE":
        return 3
    root = instance_root(group.name)
    # The WRITE timing source is a local replica of SENSE's final restored
    # state.  Place it beside the SENSE taper so only its high-impedance
    # isolated output crosses to the write lane.
    if root.startswith("XWSRC"):
        return 2
    if root in ("XP06S", "XP09M", "XP10"):
        return 1
    if root in ("XP08", "XPMD", "XPLC", "XPLD"):
        return 3
    if root == "XLEGACY":
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


def place(devices: list[Device], groups: dict[str, Group],
          expanded_local_spacing: bool = False) -> tuple[float, dict[str, float]]:
    even_depth = group_depths(groups, "E")
    even = [group for group in groups.values() if group.phase == "E"]
    cluster_depth = {}
    for prefix in ("XCM", "XSM", "XWM", "XWE"):
        selected = [group for group in even
                    if re.fullmatch(prefix + r"[0-3](?:[A-C])?",
                                    instance_root(group.name))]
        target = max((even_depth[group.name] for group in selected), default=0)
        cluster_depth.update({group.name: target for group in selected})
    place_depth = {group.name: cluster_depth.get(group.name, even_depth[group.name])
                   for group in even}
    ordered = sorted(even, key=lambda group: (place_depth[group.name], group.name))
    group_x: dict[str, float] = {}
    lane_ends = []
    for lane in range(LANE_COUNT):
        # Offset the write lane from the 7+28n um global strap grid while
        # keeping its delay producers, selectors, and restorers compact.  An
        # earlier 202-um lead-in added roughly 190 um of needless timing-net
        # route before the first device and dominated exact extracted RC.
        # Offset the compact sense lane from the 7+28n um rail-via grid.  The
        # strengthened profile-3 selector otherwise spans the x=91 um strap,
        # leaving no legal metal2 drain-access segment.
        cursor = 34.0 if lane == 3 else (14.0 if lane == 2 else 12.0)
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
            write_taps = ("XPG3N", "XPG3I", "XPMD3", "XP09M", "XP10")
            write_rank = {name: rank for rank, name in enumerate(write_taps)}
            write_min_x = {"XPG3N": 130.0, "XPG3I": 140.0,
                           "XPMD3": 153.68,
                           "XP09M": 198.0, "XP10": 226.0}

            def lane_one_order(group: Group) -> tuple[int, int, int, str]:
                parts = instance_path(group.name)
                root = parts[0]
                stage = (int(parts[1][2:])
                         if len(parts) > 1
                         and re.fullmatch(r"X[ID]\d+", parts[1]) else 0)
                if root in write_rank:
                    return (1, write_rank[root], stage, group.name)
                return (0, place_depth[group.name], 0, group.name)

            selected.sort(key=lane_one_order)
        if lane == 2:
            # PCLK and the selected delayed replica feed a small local NOR;
            # the following taper, not either timing net, drives the large
            # regenerative gate load.
            sense_rank = {
                "XPC": 0,
                "XSM0A": 1, "XSM0B": 2,
                "XSM2A": 3, "XSM2B": 4,
                "XSM3A": 5, "XSM3B": 6, "XSM3C": 7,
                "XSMR": 8,
                "XSN": 10, "XHSD0": 11, "XHSD1": 12,
                "XHSN": 13, "XSB0": 14, "XRB0": 15, "XRBI": 16,
                "XSB1": 17, "XRB1": 18, "XRBB": 19,
                "XSB2": 20, "XRB2": 21, "XWSRC": 22, "XWSRCC": 23,
            }

            def sense_order(group: Group) -> tuple[int, int, int, str]:
                parts = instance_path(group.name)
                root = parts[0]
                stage = int(parts[1].removeprefix("XI")) \
                    if len(parts) > 1 and re.fullmatch(r"XI\d+", parts[1]) else 0
                if root.startswith("XCT"):
                    block = {"XCTP": 0, "XCTA": 2, "XCTB": 4}.get(root, 0)
                    return (9, block + stage, 0, group.name)
                if root == "XST":
                    # Keep the compact restored path together and put its
                    # final driver immediately before the local NOR.
                    substage = {"XI0": 4, "XC": 5, "XI1": 6}.get(
                        parts[1], 5)
                    return (9, substage, 0, group.name)
                if root == "XSN":
                    substage = {"XIA": 0, "XIB": 1, "XN": 2,
                                "XIY": 3}.get(parts[1], 4)
                    return (10, substage, 0, group.name)
                return (sense_rank.get(root, 20), 0, place_depth[group.name],
                        group.name)

            selected.sort(key=sense_order)
        if lane == 3:
            # Interleave the active restoring start/end selector cells.  Keep
            # the local P08-to-P09W delay directly between the mid-profile
            # cells, then place the matched restoration stages together.
            # Place the delay producers first, then make each shared TG node a
            # compact local cluster with its restoring buffer.  Spreading the
            # three start drivers around the delay cells left WSTART_SEL on a
            # long RC route and reduced the extracted restorer input below a
            # valid CMOS level despite a full-swing schematic source.
            selector_rank = {
                "XLEGACY": 0,
                "XP08": 1,
                # Align each dynamic cluster below its tap-local prebuffer.
                "XWM3A": 2, "XWE3A": 3,
                "XWM1": 5, "XWST": 6,
                "XPMD": 7, "XWE1": 8,
                "XPLC": 9, "XWM3": 10,
                "XWET": 11,
                "XPLD": 12, "XWE3": 13,
                # Static one-hot decode may sit after the dynamic edge path.
                "XWC0": 14, "XWC3": 15,
                "XWMCB": 16, "XWMCI": 17,
                # Selected hierarchical HCLK implementation. Each producer is
                # immediately followed by its consumer so HEMUX, HBASE, WIN,
                # and the taper inputs do not span the whole write lane.
                "XI_SEL": 0, "XI_ESEL": 1,
                "XSLOW0": 2, "XSLOW1": 3,
                "XETG0": 4, "XETG1": 5, "XEPOCHR": 6,
                "XBTG0": 7, "XBTG1": 8,
                "XST0": 9, "XST1": 10,
                "XSTR0": 11, "XSTR1": 12,
                "XEND0": 13, "XEND1A": 14, "XEND1B": 15,
                "XTG0": 16, "XTG1": 17, "XENDR": 18,
                "XDET": 19,
                "XWB0": 20, "XWB1": 21, "XWB2": 22,
                "XWB3": 23, "XWB4": 24,
            }
            if any(instance_root(group.name) == "XTD0" for group in selected):
                # Retimed full-swing implementation. Decode is outside the
                # event path; full-duty epoch states, compact taps, matched
                # restorers, and taper remain in causal order. Keep this
                # topology-local so historical layout hashes do not move.
                selector_rank.update({
                    "XLN": 2, "XLI": 3, "XNN": 4, "XNI": 5,
                    "XED0": 6, "XED1": 7,
                    "XETG0": 8, "XETG1": 9, "XETG2": 10,
                    "XEB0": 11, "XEB1": 12,
                    "XTD0": 13, "XSR0": 14, "XSR1": 15,
                    "XTD1": 16, "XTD2": 17,
                    "XTG0": 18, "XTG1": 19,
                    "XER0": 20, "XER1": 21,
                    "XDET": 22, "XWPN": 23,
                    "XWB0": 24, "XWB1": 25, "XWB2": 26,
                    "XWB3": 27, "XWB4": 28,
                })
            selector_min_x = {"XLEGACY": 130.0,
                              "XWM3A": 145.0, "XWE3A": 161.28,
                              "XWM1": 205.0,
                              "XPLC": 236.0}

            def write_order(group: Group) -> tuple[int, int, int, str]:
                parts = instance_path(group.name)
                root = parts[0]
                if (root == "XWET" and len(parts) > 1
                        and parts[1] == "XNF"):
                    # Preserve the calibrated XWET pair and downstream x
                    # coordinates by using the reserved selector whitespace.
                    return (0, 4 * 4, 0, group.name)
                if root in selector_rank:
                    numeric_stage = (re.fullmatch(r"X(?:I|D)(\d+)", parts[1])
                                     if len(parts) > 1 else None)
                    named_stage = {"XIA": 0, "XIB": 1, "XN": 2,
                                   "XIY": 3, "XN0": 0, "XN1": 1}
                    stage = (int(numeric_stage.group(1)) if numeric_stage
                             else named_stage.get(parts[1], 0)
                             if len(parts) > 1 else 0)
                    return (0, 4 * selector_rank[root] + stage, 0,
                            group.name)
                delay_match = re.fullmatch(r"XW([SE])D([0-5])", root)
                if delay_match:
                    pair = int(delay_match.group(2))
                    side = int(delay_match.group(1) == "E")
                    stage = int(parts[1].removeprefix("XD"))
                    # Interleave corresponding start/end delay cells so the
                    # six-unit transport paths see the same gradient and wire
                    # environment.
                    return (1, 4 * pair + 2 * side + stage, 0, group.name)
                if root in ("XWST", "XWET"):
                    stage = (int(parts[1].removeprefix("XI"))
                             if len(parts) > 1 and parts[1].startswith("XI")
                             else 1.5)
                    return (2, 2 * stage + int(root == "XWET"), 0,
                            group.name)
                return (3, place_depth[group.name], 0, group.name)

            selected.sort(key=write_order)
        for group in selected:
            root = instance_root(group.name)
            if lane == 1 and root in write_rank:
                cursor = max(cursor, write_min_x[root])
            if lane == 3 and root in selector_min_x:
                cursor = max(cursor, selector_min_x[root])
            if lane == 3 and root == "XPLC":
                cursor += 4.0
            if lane == 3 and root == "XPMD":
                cursor += 2.0
            if lane == 3 and root == "XWST":
                cursor += 2.0
            x = cursor
            width, offsets_by_name = group_geometry(group)
            group_x[group.name] = x
            odd_name = "XO" + group.name.removeprefix("XE")
            odd_width, odd_offsets_by_name = group_geometry(groups[odd_name])
            width = max(width, odd_width)
            group_x[odd_name] = x
            for phase_name in (group.name, odd_name):
                for device in groups[phase_name].devices:
                    device.lane = lane
                    even_name = ("XE" + device.name.removeprefix("XO")
                                 if device.name.startswith("XO") else device.name)
                    offsets = (odd_offsets_by_name if phase_name == odd_name
                               else offsets_by_name)
                    lookup_name = (device.name if phase_name == odd_name
                                   else even_name)
                    device.cx = x + offsets[lookup_name]
                    base = LANE_PITCH * lane
                    if group.primitive in ("cp_cond_npd", "cp_cond_npd_comp"):
                        # Keep wide conditional pull-downs below the pwell/
                        # nwell boundary while preserving the common top edge
                        # used by their Metal2 access pattern.
                        device.cy = base - max(0.0,
                                               (device.width_um - 10.0) / 2.0)
                    else:
                        p_shift = (max(0.0, (device.width_um - 10.0) / 2.0)
                                   if device.kind.startswith("pfet") else 0.0)
                        n_shift = (max(0.0, (device.width_um - 10.0) / 2.0)
                                   if device.kind.startswith("nfet") else 0.0)
                        device.cy = base + (12.0 + p_shift
                                            if device.kind.startswith("pfet")
                                            else -n_shift)
            # The logic/mux lanes are dominated by local RC, so use a compact
            # standard-cell-like channel.  Delay/prebuffer lanes retain the
            # wider channel needed by their many cross-lane tap routes.
            if expanded_local_spacing:
                gap = 2.5 if lane == 3 else (3.0 if lane == 2 else 4.0)
            else:
                gap = 1.0 if lane == 3 else (2.0 if lane == 2 else 4.0)
            cursor = x + width + gap
        lane_ends.append(cursor)
    phase_width = max(lane_ends) + 10.0
    for device in devices:
        if device.phase == "O":
            device.cy += PHASE_Y_SHIFT
    return phase_width, group_x


def tcl_header(cell_name: str) -> str:
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
proc supply_stack34 {x y} {
    rect metal3 [expr {$x-0.70}] [expr {$y-0.70}] [expr {$x+0.70}] [expr {$y+0.70}]
    rect metal4 [expr {$x-0.70}] [expr {$y-0.70}] [expr {$x+0.70}] [expr {$y+0.70}]
    foreach dx {-0.30 0.30} {
        foreach dy {-0.30 0.30} { via_at via3 [expr {$x+$dx}] [expr {$y+$dy}] }
    }
}
proc supply_stack45 {x y} {
    rect metal4 [expr {$x-0.70}] [expr {$y-0.70}] [expr {$x+0.70}] [expr {$y+0.70}]
    rect metal5 [expr {$x-0.80}] [expr {$y-0.80}] [expr {$x+0.80}] [expr {$y+0.80}]
    foreach dx {-0.30 0.30} {
        foreach dy {-0.30 0.30} { via_at via4 [expr {$x+$dx}] [expr {$y+$dy}] }
    }
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
proc make_port4 {name number x y} {
    rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    box values [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    label $name FreeSans 0.5 0 0 0 c metal4
    port make $number
}
proc make_supply_port {name number x y} {
    rect metal5 [expr {$x-3.00}] [expr {$y-3.00}] [expr {$x+3.00}] [expr {$y+3.00}]
    box values [expr {$x-3.00}] [expr {$y-3.00}] [expr {$x+3.00}] [expr {$y+3.00}]
    label $name FreeSans 0.5 0 0 0 c metal5
    port make $number
}
proc make_supply_port4 {name number x y} {
    rect metal4 [expr {$x-0.75}] [expr {$y-0.75}] [expr {$x+0.75}] [expr {$y+0.75}]
    box values [expr {$x-0.75}] [expr {$y-0.75}] [expr {$x+0.75}] [expr {$y+0.75}]
    label $name FreeSans 0.5 0 0 0 c metal4
    port make $number
}
crashbackups stop
load @CELL_NAME@
units microns
'''.replace("@CELL_NAME@", cell_name)


def route_columns(devices: list[Device], reserved: list[float],
                  tracks: dict[str, float], min_column_spacing: float = 0.86,
                  reserve_tap_columns_globally: bool = False
                  ) -> dict[tuple[str, str], float]:
    occupied: dict[str, list[tuple[float, float, float, str]]] = {
        phase: [] for phase in ("E", "O")}
    metal2_occupied: dict[str, list[tuple[float, float, float, float, str]]] = {
        phase: [] for phase in ("E", "O")}
    for phase in ("E", "O"):
        phase_offset = PHASE_Y_SHIFT if phase == "O" else 0.0
        for x in reserved:
            if reserve_tap_columns_globally:
                occupied[phase].append(
                    (x, phase_offset - 10.0,
                     phase_offset + LANE_PITCH * LANE_COUNT + 26.0,
                     "__TAP_RESERVED__"))
            for lane in range(LANE_COUNT):
                base = LANE_PITCH * lane
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
        gate_x_nudge = 0.1 if "__XWB4__" in device.name else 0.0
        # Transmission-gate PMOS/NMOS gates are complementary nets. Their
        # devices are deliberately vertically aligned, so give the two gate
        # access columns opposite horizontal nudges in the new nested WRITE
        # hierarchy instead of stacking different nets on one column.
        if ("__XWRITE__" in device.name
                and re.search(r"__X(?:B|E)?TG\d+__", device.name)):
            gate_x_nudge = 0.9 if device.kind.startswith("pfet") else -0.9
        preferred = {"D": device.cx - span / 2.0 - 0.75,
                     "G": device.cx + gate_x_nudge,
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
                        (old_net == net and abs(candidate - old_x) < 1e-6)
                        or abs(candidate - old_x) >= min_column_spacing
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
                metal2_blockers = [(old_net, tuple(round(value, 3) for value
                                                   in (old_x1, old_y1,
                                                       old_x2, old_y2)))
                                   for old_x1, old_y1, old_x2,
                                   old_y2, old_net
                                   in metal2_occupied[device.phase]
                                   if old_net != net
                                   and candidate_metal2[2] + 0.28 > old_x1
                                   and old_x2 + 0.28 > candidate_metal2[0]
                                   and candidate_metal2[3] + 0.28 > old_y1
                                   and old_y2 + 0.28 > candidate_metal2[1]][:6]
                raise RuntimeError(
                    f"no access column for {device.name} {terminal}; "
                    f"terminal_y={terminal_y[terminal]:.3f}, "
                    f"points={[round(point, 3) for point in points]}, "
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


def interval_lanes(keys: list[str], bounds: dict[str, list[float]],
                   fixed: dict[str, int] | None = None,
                   blocked: dict[int, list[tuple[float, float]]] | None = None
                   ) -> dict[str, int]:
    fixed = fixed or {}
    blocked = blocked or {}
    fixed_intervals: dict[int, list[tuple[float, float]]] = {}
    for key, lane in fixed.items():
        fixed_intervals.setdefault(lane, []).append(tuple(bounds[key]))
    lane_ends: list[float] = [-math.inf] * (
        max(fixed.values(), default=-1) + 1)
    answer: dict[str, int] = {}
    for key in sorted(keys, key=lambda item: (bounds[item][0], bounds[item][1])):
        start, end = bounds[key]
        lane = fixed.get(key)
        if lane is not None and lane_ends[lane] + 1.4 > start:
            raise RuntimeError(f"fixed route lane conflict at {key}")
        if lane is None:
            lane = next((index for index, old_end in enumerate(lane_ends)
                         if old_end + 1.4 <= start
                         and all(end + 1.4 <= fixed_start
                                 or fixed_end + 1.4 <= start
                                 for fixed_start, fixed_end
                                 in fixed_intervals.get(index, []))
                         and all(end + 1.4 <= blocked_start
                                 or blocked_end + 1.4 <= start
                                 for blocked_start, blocked_end
                                 in blocked.get(index, []))),
                        len(lane_ends))
        if lane == len(lane_ends):
            lane_ends.append(end)
        else:
            lane_ends[lane] = end
        answer[key] = lane
    return answer


def emit(source: Path, output: Path, top_name: str = "clock_pulse_generator") -> None:
    subckts = parse(source)
    if top_name not in subckts:
        raise ValueError(f"top subcircuit {top_name!r} not found")
    devices, groups = flatten(subckts, top_name)
    xmax, group_x = place(
        devices, groups,
        expanded_local_spacing=(top_name != "clock_pulse_generator"))
    tap_xs = [x for x in frange(7.0, xmax - 4.0, 28.0)
              if all(abs(x - device.cx) >= device_span(device) / 2.0 + 1.2
                     for device in devices)]
    if not tap_xs:
        raise RuntimeError("placement leaves no legal substrate-tap column")
    first_seen: dict[str, int] = {}
    key_lane_sets: dict[str, set[int]] = {}
    key_phase_sets: dict[str, set[str]] = {}
    for device in devices:
        for net in device.nodes[:3]:
            key = route_key(device, net)
            first_seen.setdefault(key, len(first_seen))
            key_lane_sets.setdefault(key, set()).add(device.lane)
            key_phase_sets.setdefault(key, set()).add(device.phase)
    special_tracks = {
        f"{phase}{lane}:{rail}": offset + LANE_PITCH * lane + rail_offset
        for phase, offset in (("E", 0.0), ("O", PHASE_Y_SHIFT))
        for lane in range(LANE_COUNT)
        for rail, rail_offset in (("VSS", -8.0), ("VDD", 21.0))
    }
    # Reserve the added hierarchical hot-clock taps outside the allocator's
    # existing lane-1 signal slots.  Letting these two nets participate in the
    # interval coloring reshuffled otherwise unchanged write routes and erased
    # the previously proven nominal PEX behavior.
    special_signal_tracks = {"CLKP_H", "CLKN_H"}
    # Center these just above each phase's lane-0 VSS rail.
    special_tracks.update({"CLKP_H": -4.0,
                           "CLKN_H": -4.0 + PHASE_Y_SHIFT})
    # The write-selector outputs switch in opposite directions and are both
    # degraded by an enabled transmission gate.  Keep their long metal4 runs
    # at opposite edges of the lane instead of on adjacent tracks; extraction
    # of the adjacent version showed 5.14 fF of mutual capacitance.
    fixed_signal_tracks = {
        "E:SEL3": 30.7, "E:SEL2": 32.8,
        "E:SEL1": 34.9, "E:SEL0": 39.1,
        "O:SEL3": 30.7 + PHASE_Y_SHIFT,
        "O:SEL2": 32.8 + PHASE_Y_SHIFT,
        "O:SEL1": 34.9 + PHASE_Y_SHIFT,
        "O:SEL0": 39.1 + PHASE_Y_SHIFT,
        # Avoid 89.5/249.5: those are also the allocator's lane-3 track zero.
        # Reusing that ordinate can create a DRC-clean electrical short when
        # a different local net happens to receive slot zero.
        "XE__WSTART_SEL": LANE_PITCH * (LANE_COUNT - 1) - 11.0,
        "XE__WEND_SEL": LANE_PITCH * (LANE_COUNT - 1) + 18.0,
        "XO__WSTART_SEL": (LANE_PITCH * (LANE_COUNT - 1) - 11.0
                            + PHASE_Y_SHIFT),
        "XO__WEND_SEL": (LANE_PITCH * (LANE_COUNT - 1) + 18.0
                          + PHASE_Y_SHIFT),
        # XPMD3 restores locally in lane 1, but its output runs on the proven
        # lane-3 ordinate shared (over disjoint x intervals) with WMID.
        "XE__P09S": 109.0,
        "XO__P09S": 109.0 + PHASE_Y_SHIFT,
        "XE__WMID": 109.0, "XE__WMIDB": 106.9, "XE__WB0": 111.1,
        "XO__WMID": 109.0 + PHASE_Y_SHIFT,
        "XO__WMIDB": 106.9 + PHASE_Y_SHIFT,
        "XO__WB0": 111.1 + PHASE_Y_SHIFT,
        # The final inverter has NMOS diffusion stacks on the generic 104.8
        # ordinate. Keep its gate net on the adjacent track; WB2 occupies the
        # same ordinate only over a disjoint x interval.
        "XE__WB4": 113.0,
        "XO__WB4": 113.0 + PHASE_Y_SHIFT,
        # Dedicated final-sense ground tracks occupy the otherwise empty
        # boundary below lane 2.  Keeping them off the global VSS ordinate
        # preserves separate LVS nets while allowing a 3-um M4 path.
        "VSS_SE": LANE_PITCH * 2 - 11.5,
        "VSS_SO": LANE_PITCH * 2 - 11.5 + PHASE_Y_SHIFT,
        # Keep the local final-stage supply clear of the large NMOS drain
        # contact array. The generic allocator can otherwise choose 111.1 um,
        # placing the supply route directly beside an output contact stack.
        "VDD_WE": 115.3,
        "VDD_WO": 115.3 + PHASE_Y_SHIFT,
    }
    signal_keys = [key for key in first_seen if key not in special_tracks]
    precolored_local_lanes = {
        "E:SEL3": 0, "O:SEL3": 0,
        "E:SEL2": 1, "O:SEL2": 1,
        "E:SEL1": 2, "O:SEL1": 2,
        "E:SEL0": 4, "O:SEL0": 4,
        # Keep the long D08 write epoch clear of the expanded HCLK Metal5
        # landing set.  Local lane 3 is disjoint from the other group-0 route
        # over D08's exact x interval.
        "XE__D08": 3, "XO__D08": 3,
        "XE__D10": 5, "XO__D10": 5,
        "XE__P09S": 3, "XO__P09S": 3,
        "XE__WMID": 3, "XO__WMID": 3,
        "XE__WMIDB": 2, "XO__WMIDB": 2,
        "XE__WB0": 4, "XO__WB0": 4,
        "XE__WB4": 0, "XO__WB4": 0,
    }
    approximate_bounds: dict[str, list[float]] = {
        key: [math.inf, -math.inf]
        for key in set(special_tracks) | set(first_seen)}
    debug_labels = {
        "XE__D08": "DBG_E_D08", "XE__D09": "DBG_E_D09",
        "XE__WSTART_SEL": "DBG_E_WSTART_SEL",
        "XE__WEND_SEL": "DBG_E_WEND_SEL",
        "XE__WST": "DBG_E_WST", "XE__WET": "DBG_E_WET",
        "XE__WCOREB": "DBG_E_WCOREB",
        "XE__WB0": "DBG_E_WB0",
        "XE__WB1": "DBG_E_WB1", "XE__WB2": "DBG_E_WB2",
        "XE__WB3": "DBG_E_WB3", "XE__SSEL": "DBG_E_SSEL",
        "XE__P06_G": "DBG_E_P06G", "XE__P06S": "DBG_E_P06S",
        "XE__P09S": "DBG_E_P09S",
        "XE__P09M": "DBG_E_P09M", "XE__P10M": "DBG_E_P10M",
        "XE__WMID": "DBG_E_WMID", "XE__WMIDB": "DBG_E_WMIDB",
        "XE__CT": "DBG_E_CT", "XE__ST": "DBG_E_ST",
        "XE__CTD": "DBG_E_CTD", "XE__STD": "DBG_E_STD",
        "XE__SN0": "DBG_E_SN0", "XE__SND": "DBG_E_SND",
        "XE__HSM": "DBG_E_HSM", "XE__HSD": "DBG_E_HSD",
        "XE__HSDX": "DBG_E_HSDX", "XE__HSN": "DBG_E_HSN",
        "XE__RB0": "DBG_E_RB0", "XE__RB1": "DBG_E_RB1",
        "XE__WGS": "DBG_E_WGS", "XE__WWE": "DBG_E_WWE",
        "XE__WSIB": "DBG_E_WSIB", "XE__WSA": "DBG_E_WSA",
        "XE__WSB": "DBG_E_WSB", "XE__WSR": "DBG_E_WSR",
        "XE__WSD": "DBG_E_WSD", "XE__WPN": "DBG_E_WPN",
        "XE__SB0": "DBG_E_SB0",
        "XE__SB1": "DBG_E_SB1",
        "XE__PCLK": "DBG_E_PCLK", "XE__P08": "DBG_E_P08",
        "XE__CTSEL": "DBG_E_CTSEL",
        "XE__XCT__B0": "DBG_E_CTB0", "XE__XCT__B1": "DBG_E_CTB1",
        "XE__XCT__B2": "DBG_E_CTB2", "XE__XST__B0": "DBG_E_STB0",
        "XE__XST__B1": "DBG_E_STB1", "XE__XST__B2": "DBG_E_STB2",
        "XE__XWST__B1": "DBG_E_WSTB1",
        "XE__XWET__B1": "DBG_E_WETB1",
        "XO__P08": "DBG_O_P08",
        "XO__PCLK": "DBG_O_PCLK",
        "XO__D08": "DBG_O_D08",
        "XO__WSTART_SEL": "DBG_O_WSTART_SEL",
        "XO__WEND_SEL": "DBG_O_WEND_SEL",
        "XO__WST": "DBG_O_WST", "XO__WET": "DBG_O_WET",
        "XO__WCOREB": "DBG_O_WCOREB", "XO__WB0": "DBG_O_WB0",
        "XO__WB1": "DBG_O_WB1", "XO__WB2": "DBG_O_WB2",
        "XO__WB3": "DBG_O_WB3",
        "XO__SSEL": "DBG_O_SSEL", "XO__CT": "DBG_O_CT",
        "XO__ST": "DBG_O_ST", "XO__CTD": "DBG_O_CTD",
        "XO__STD": "DBG_O_STD",
        "XO__SN0": "DBG_O_SN0", "XO__SND": "DBG_O_SND",
        "XO__HSM": "DBG_O_HSM", "XO__HSD": "DBG_O_HSD",
        "XO__HSDX": "DBG_O_HSDX", "XO__HSN": "DBG_O_HSN",
        "XO__RB0": "DBG_O_RB0", "XO__RB1": "DBG_O_RB1",
        "XO__WGS": "DBG_O_WGS", "XO__WWE": "DBG_O_WWE",
        "XO__WSIB": "DBG_O_WSIB", "XO__WSA": "DBG_O_WSA",
        "XO__WSB": "DBG_O_WSB", "XO__WSR": "DBG_O_WSR",
        "XO__WSD": "DBG_O_WSD", "XO__WPN": "DBG_O_WPN",
        "XO__SB0": "DBG_O_SB0",
        "XO__SB1": "DBG_O_SB1",
        "XO__XWST__B1": "DBG_O_WSTB1",
        "XO__XWET__B1": "DBG_O_WETB1",
        "XO__P06_G": "DBG_O_P06G", "XO__P06S": "DBG_O_P06S",
        "XO__P09S": "DBG_O_P09S",
        "XO__P09M": "DBG_O_P09M", "XO__P10M": "DBG_O_P10M",
        "XO__WMID": "DBG_O_WMID", "XO__WMIDB": "DBG_O_WMIDB",
    }

    def semantic_debug_label(key: str) -> str | None:
        """Return a stable extracted name for contract-relevant timing nets."""
        if key in debug_labels:
            return debug_labels[key]
        if key == "__E_WPN":
            return "DBG_E_WPN"
        if key == "__O_WPN":
            return "DBG_O_WPN"
        for prefix, label_prefix in (("XE__XWRITE__", "DBG_EW_"),
                                     ("XO__XWRITE__", "DBG_OW_")):
            if key.startswith(prefix):
                tail = key.removeprefix(prefix)
                # Label the parent-visible state path, not every private node
                # inside a primitive.  These names are the schematic/PEX join
                # used by counterfactual localization.
                if "__" not in tail and tail in {
                    "HSM", "HSLOW", "HEMUX", "HEPOCH", "HBASE",
                    "S0A", "S1A", "STR0", "START", "E0", "E1A",
                    "E1", "EMUX", "END", "WIN", "WB0", "WB1",
                    "WB2", "WB3", "WB4", "EDL", "EDL2", "EB0",
                    "EBASE", "T0", "T1", "T2", "ENDMUX", "SR0",
                    "ER0",
                }:
                    return label_prefix + tail
        return None
    for device in devices:
        span = device_span(device) + 2.0
        for net in device.nodes[:3]:
            key = route_key(device, net)
            approximate_bounds[key][0] = min(approximate_bounds[key][0],
                                             device.cx - span)
            approximate_bounds[key][1] = max(approximate_bounds[key][1],
                                             device.cx + span)

    top_ports = subckts[top_name].ports
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
    # Give the high-current supply spines enough separation for 5-um Metal3.
    port_xs.update({"VDD": -20.0, "VSS": -28.0})
    port_xs.update({"VSS_SE": xmax + 4.0, "VSS_SO": xmax + 4.0})
    port_xs.update({port: xmax + 2.0 + 2.0 * index
                    for index, port in enumerate(output_ports)})
    # The dedicated full-swing clock taps are parent-strapped copies of
    # CLKP/CLKN. Place them beside the first HCLK delay receiver rather than
    # forcing that clock load through the macro's long legacy-clock route.
    if "XE__XPG3N" in group_x:
        hclk_receiver = "XE__XPG3N"
    else:
        hclk_candidates = sorted(
            name for name in group_x if name.startswith("XE__XHSD0__"))
        if not hclk_candidates:
            raise RuntimeError("cannot locate even-phase HCLK receiver")
        hclk_receiver = hclk_candidates[0]
    hot_clock_x = group_x[hclk_receiver] - 10.0
    port_xs.update({"CLKP_H": hot_clock_x, "CLKN_H": hot_clock_x})
    def driver(phase: str, instance: str) -> str:
        candidates = [name for name in groups
                      if name.startswith(phase) and name.endswith("__" + instance)]
        if len(candidates) != 1:
            raise RuntimeError(
                f"expected one {phase} {instance} driver, got {candidates}")
        return candidates[0]

    output_drivers = {
        "E_SENSE": driver("XE", "XSB2"),
        "E_BOOST": driver("XE", "XRB2"),
        "E_WRITE": driver("XE", "XWB4"),
        "O_SENSE": driver("XO", "XSB2"),
        "O_BOOST": driver("XO", "XRB2"),
        "O_WRITE": driver("XO", "XWB4"),
    }
    for port, driver in output_drivers.items():
        width, _ = group_geometry(groups[driver])
        port_xs[port] = group_x[driver] + width + 2.0
    even_write_driver = output_drivers["E_WRITE"]
    write_driver_width, _ = group_geometry(groups[even_write_driver])
    write_supply_x = group_x[even_write_driver] + write_driver_width / 2.0
    port_xs.update({"VDD_WE": write_supply_x, "VDD_WO": write_supply_x})
    for port, keys in top_keys.items():
        endpoint = port_xs[port]
        for key in keys:
            approximate_bounds[key][0] = min(approximate_bounds[key][0], endpoint)
            approximate_bounds[key][1] = max(approximate_bounds[key][1], endpoint)
    # Phase is semantic provenance, not a naming convention.  In particular,
    # a top-local odd net is flattened as ``__O_WPN`` and does not start with
    # any of the historical XO/O_ prefixes.  Classifying it by spelling put
    # its Metal4 route in the even band and produced a DRC-clean phase short.
    mixed_signal_keys = sorted(
        key for key in signal_keys if len(key_phase_sets[key]) != 1)
    if mixed_signal_keys:
        raise RuntimeError(
            "cross-phase signal keys must be split by route_key: "
            f"{mixed_signal_keys}")
    even_keys = [key for key in signal_keys
                 if key_phase_sets[key] == {"E"}]
    odd_keys = [key for key in signal_keys
                if key_phase_sets[key] == {"O"}]
    key_groups = {key: min(key_lane_sets[key]) for key in signal_keys}

    hclk_landing_blocks = {
        phase: [(device.cx - 8.0, device.cx + 8.0)
                for device in devices
                if device.phase == phase
                and device.nodes[1] in ("CLKP_H", "CLKN_H")]
        for phase in ("E", "O")
    }

    def grouped_lanes(keys: list[str], routing_bounds: dict[str, list[float]],
                      phase: str):
        answer = {}
        for group in range(LANE_COUNT):
            grouped_keys = [key for key in keys if key_groups[key] == group]
            local = interval_lanes(
                grouped_keys, routing_bounds,
                {key: lane for key, lane in precolored_local_lanes.items()
                 if key in grouped_keys},
                {1: hclk_landing_blocks[phase]} if group == 0 else None)
            answer.update({key: 100 * group + lane for key, lane in local.items()})
        return answer

    def track_y(code: int, odd_phase: bool) -> float:
        group, local_lane = divmod(code, 100)
        if local_lane >= 13:
            raise RuntimeError(f"routing band {group} exceeds 13 tracks per phase")
        return (-5.3 + LANE_PITCH * group + 2.1 * local_lane
                + PHASE_Y_SHIFT * int(odd_phase))

    def assign_tracks(routing_bounds: dict[str, list[float]]):
        even = grouped_lanes(even_keys, routing_bounds, "E")
        odd = grouped_lanes(odd_keys, routing_bounds, "O")
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
    new_top = top_name != "clock_pulse_generator"
    for _ in range(32):
        columns = route_columns(
            devices, tap_xs, tracks,
            min_column_spacing=(1.10 if new_top else 0.86),
            reserve_tap_columns_globally=new_top)
        # The PMOS/NMOS input gates of the local hot-clock NAND are vertically
        # aligned and carry the same net.  Share their Metal3 access column;
        # the generic collision allocator intentionally does not assume
        # same-net merging and otherwise puts the second access needlessly
        # close to an unrelated lane-0 Metal4 route.
        for device in devices:
            if "__XPG3N__" in device.name \
                    and device.nodes[1] in ("CLKP_H", "CLKN_H"):
                columns[(device.name, "G")] = device.cx
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
            move_keys.difference_update(precolored_local_lanes)
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

    lines = [tcl_header(top_name)]
    for phase_offset in (0.0, PHASE_Y_SHIFT):
        for lane in range(LANE_COUNT):
            base = LANE_PITCH * lane
            base += phase_offset
            lines.append(f"rect pwell 2 {base-8:.3f} {xmax:.3f} {base+6:.3f}\n")
            # Wide PMOS fingers are shifted upward to preserve the common
            # source/drain channel.  A 16 um finger reaches base+23.0; retain
            # 0.50 um of N-well enclosure, above the 0.43 um DF.7 minimum,
            # while leaving 0.50 um before the next lane's P-well band.
            lines.append(f"rect nwell 2 {base+6.4:.3f} {xmax:.3f} {base+24.5:.3f}\n")
    for device in devices:
        lines.append(f"draw_mos {device.kind} {device.width_um:.6f} {device.mult} "
                     f"{device.cx:.3f} {device.cy:.3f}\n")
    group_route_columns = {
        group: [columns[(member.name, terminal)]
                for member in devices if member.group == group
                for terminal in ("D", "G", "S")]
        for group in {device.group for device in devices}
    }
    group_source_samples = {
        group: [point
                for member in devices if member.group == group
                for points in [[member.cx + x for x in offsets(member.mult, 1)]]
                for index in sorted({round(i * (len(points) - 1) / 4)
                                     for i in range(5)})
                for point in [points[index]]]
        for group in {device.group for device in devices}
    }
    drain_access_columns: dict[str, list[float]] = {}
    for device in devices:
        width = device.width_um
        nf = device.mult
        root = instance_root(device.group)
        d_y = device.cy + max(0.70, width / 2.0 - 0.8)
        # The final PMOS bank formerly picked every source up near the lower
        # edge of its 8-um diffusion stripe.  Exact PEX attributed about
        # 10.9 ohm of the port-to-source path to the resulting two local
        # access segments.  Land this high-current source strap at the device
        # center; it crosses alternating drain Metal1 without contacting it
        # and reaches each source diffusion through its own via1.
        s_y = (device.cy if ((root == "XWB4" and device.kind.startswith("pfet"))
                             or (root == "XSB2" and device.kind.startswith("nfet")))
               else device.cy - max(0.70, width / 2.0 - 0.8))
        d_points = [device.cx + x for x in offsets(nf, 0)]
        s_points = [device.cx + x for x in offsets(nf, 1)]
        gate_y = device.cy - width / 2.0 - 0.70 - gate_extra(device)
        source_access_columns: list[float] = []
        for terminal, net, y, points in (("D", device.nodes[0], d_y, d_points),
                                         ("S", device.nodes[2], s_y, s_points)):
            distributed_columns = (drain_access_columns.setdefault(device.group, [])
                                   if terminal == "D" else source_access_columns)
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
            if (terminal == "S" and root == "XWB4" and net == "VDD"
                    and min(abs(route_x - tap_x) for tap_x in tap_xs) >= 1.2):
                lines.append(f"supply_stack45 {route_x:.3f} {ty:.3f}\n")
            if terminal in ("D", "S") and root == "XWB4" and len(points) >= 5:
                # The loaded write banks cannot funnel their current through
                # one minimum-width Metal3 access. Fan the already-connected
                # Metal2 diffusion straps into independent columns.
                sample_indices = (list(range(len(points))) if terminal == "D"
                                  else sorted({round(i * (len(points) - 1) / 4)
                                               for i in range(5)}))
                blocked = ([*group_route_columns[device.group],
                            *group_source_samples[device.group], *tap_xs]
                           if terminal == "D" else
                           [columns[(device.name, "D")],
                            columns[(device.name, "G")],
                            columns[(device.name, "S")],
                            *drain_access_columns[device.group]])
                blocked.extend([route_x, *distributed_columns])
                for access_x in (points[i] for i in sample_indices):
                    if any(abs(access_x - old_x) < 0.86 for old_x in blocked):
                        continue
                    lines.append(f"stack23 {access_x:.3f} {y:.3f}\n")
                    lines.append(f"rect metal3 {access_x-0.28:.3f} "
                                 f"{min(y,ty)-0.28:.3f} "
                                 f"{access_x+0.28:.3f} "
                                 f"{max(y,ty)+0.28:.3f}\n")
                    lines.append(f"stack34 {access_x:.3f} {ty:.3f}\n")
                    if (terminal == "S" and net == "VDD"
                            and min(abs(access_x - tap_x)
                                    for tap_x in tap_xs) >= 1.2):
                        lines.append(f"supply_stack45 {access_x:.3f} {ty:.3f}\n")
                    blocked.append(access_x)
                    distributed_columns.append(access_x)
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

    # exact_bounds is intentionally assembled from sets because it is used as
    # a lookup table.  Never let that hash-random insertion order leak into
    # the generated layout source: identical geometry must be byte-for-byte
    # reproducible across Python processes and container hash seeds.
    for key in sorted(bounds, key=lambda item: (first_seen.get(item, -1), item)):
        x1, x2 = bounds[key]
        y = tracks[key]
        half = (2.00 if key.endswith((":VDD", ":VSS")) else
                0.75 if key in ("VSS_SE", "VSS_SO")
                else 0.38 if key in ("VDD_WE", "VDD_WO")
                else 0.38 if key in special_signal_tracks
                else 0.23)
        if key in special_tracks and key not in special_signal_tracks:
            x1 = min(x1, tap_xs[0])
            x2 = max(x2, tap_xs[-1])
        if key in ("VDD_WE", "VDD_WO"):
            # Put the large Metal4/5 port stack inside, rather than exactly on
            # the end of, its M4 strap. Coincident strap/landing boundaries
            # leave a sub-minimum notch in Magic's unioned polygon.
            x1 -= 1.0
            x2 += 1.0
        layer = "metal5" if key in special_signal_tracks else "metal4"
        x_pad = 0.38
        lines.append(f"# route {key}\n")
        lines.append(f"rect {layer} {x1-x_pad:.3f} {y-half:.3f} "
                     f"{x2+x_pad:.3f} {y+half:.3f}\n")
        if key in special_signal_tracks:
            access_columns = []
            for device in devices:
                for terminal, net in zip(("D", "G", "S"), device.nodes[:3]):
                    if route_key(device, net) == key:
                        access_columns.append(columns[(device.name, terminal)])
                        lines.append(
                            f"stack45 {columns[(device.name, terminal)]:.3f} "
                            f"{y:.3f}\n")
            # Each access gets its own stack45 landing.  Metal5 connects the
            # clock fanout; a lower-metal strap spanning all accesses becomes
            # a spacing hazard as new parent-clock consumers are added.
            access_columns = sorted(set(access_columns))
            cluster: list[float] = []
            clusters: list[list[float]] = []
            for access_x in access_columns:
                if cluster and access_x - cluster[-1] >= 1.60:
                    clusters.append(cluster)
                    cluster = []
                cluster.append(access_x)
            if cluster:
                clusters.append(cluster)
            for local_cluster in clusters:
                if len(local_cluster) > 1:
                    lines.append(
                        f"rect metal4 {local_cluster[0]-0.38:.3f} "
                        f"{y-0.38:.3f} {local_cluster[-1]+0.38:.3f} "
                        f"{y+0.38:.3f}\n")
        debug_label = semantic_debug_label(key)
        if debug_label is not None:
            label_x = (x1 + x2) / 2.0
            lines.append(f"box values {label_x-0.2:.3f} {y-0.2:.3f} "
                         f"{label_x+0.2:.3f} {y+0.2:.3f}\n")
            lines.append(f"label {debug_label} FreeSans 0.4 0 0 0 c metal4\n")

    for key in special_tracks:
        if key in special_signal_tracks:
            continue
        y = tracks[key]
        # Six-micron top-metal rails and matching port spines reduce the
        # shared supply impedance identified by exact-PEX counterfactuals.
        # Adjacent VDD/VSS rail centers remain 7 um apart at the tightest
        # lane boundary, leaving 1 um of same-layer spacing.
        lines.append(f"rect metal5 2.000 {y-3.00:.3f} "
                     f"{xmax:.3f} {y+3.00:.3f}\n")
        for x in tap_xs:
            lines.append(f"supply_stack45 {x:.3f} {y:.3f}\n")

    for phase, phase_offset in (("E", 0.0), ("O", PHASE_Y_SHIFT)):
        for lane in range(LANE_COUNT):
            phase_y = LANE_PITCH * lane + phase_offset
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
                lines.append(f"rect metal3 {x-3.00:.3f} {min(ys)-0.70:.3f} "
                             f"{x+3.00:.3f} {max(ys)+0.70:.3f}\n")
                for y in ys:
                    lines.append(f"supply_stack34 {x:.3f} {y:.3f}\n")
                lines.append(f"supply_stack34 {x:.3f} {port_y:.3f}\nsupply_stack45 {x:.3f} {port_y:.3f}\n")
            else:
                lines.append(f"rect metal5 {x-0.38:.3f} {min(ys)-0.38:.3f} {x+0.38:.3f} {max(ys)+0.38:.3f}\n")
                for y in ys:
                    lines.append(f"stack45 {x:.3f} {y:.3f}\n")
        else:
            port_y = tracks[keys[0]]
            if port in ("VSS_SE", "VSS_SO"):
                lines.append(f"make_supply_port4 {port} {index} "
                             f"{x:.3f} {port_y:.3f}\n")
                continue
            if port in output_ports:
                lines.append(f"make_port4 {port} {index} {x:.3f} {port_y:.3f}\n")
                continue
            if port not in special_signal_tracks:
                lines.append(f"stack45 {x:.3f} {port_y:.3f}\n")
        if port in ("VDD", "VSS", "VDD_WE", "VDD_WO", "VSS_SE", "VSS_SO"):
            lines.append(f"make_supply_port {port} {index} {x:.3f} {port_y:.3f}\n")
        else:
            lines.append(f"make_port {port} {index} {x:.3f} {port_y:.3f}\n")

    lines.append(f"save /work/{top_name}\n")
    lines.append(f"gds write /work/{top_name}.gds\n")
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
    parser.add_argument("--top", default="clock_pulse_generator")
    args = parser.parse_args()
    emit(args.source, args.output, args.top)


if __name__ == "__main__":
    main()
