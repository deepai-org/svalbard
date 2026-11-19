"""Resolve pad implementation inputs from the single normative architecture.

This is the generation boundary, not a second set of electrical specifications.
Geometry and transistor sizing will be implementation parameters; requested
port capacitance remains a budget to check against extraction, not a capacitor
to add on top of the physical pad.
"""
from pathlib import Path
import hashlib
import json
import math

PROJECT = Path(__file__).resolve().parents[2]

# Circuit branches are generation-time topology, not protocol profiles.
FAMILIES = {
    "reference_clock": ("refpad", ("REF_IN", "REF_IN_N"),
                        ("protection", "bias", "clock_receiver_interface")),
    "rf_receive": ("rfpad", ("RF_RX_P", "RF_RX_N"),
                   ("protection", "lna_interface")),
    "rf_transmit": ("rftxpad", ("RF_TX_P", "RF_TX_N"),
                    ("protection", "rf_driver_interface")),
    "wired_receive_usb": ("wirepad", ("WIRE_RX_P", "WIRE_RX_N"),
                          ("protection", "serial_termination", "divider", "receiver_interface",
                           "single_ended_sense", "usb_current_driver", "usb_voltage_driver",
                           "usb_termination", "pullup", "pulldown")),
    "wired_transmit": ("txpad", ("WIRE_TX_P", "WIRE_TX_N"),
                       ("protection", "serial_driver", "tmds_sink", "detect_injection",
                        "detect_sense", "power_off_isolation")),
}
STATES = ("active", "disabled", "reset", "unpowered", "brownout", "reconfiguration")


CHIPS = ("rf", "wired")


def read_bond_map(chip, text=None):
    """Sites of one chip from integration/chips/<chip>/bond_map.txt: {site: dict(side, net, instance)}."""
    if chip not in CHIPS:
        raise ValueError("Unknown chip: " + str(chip))
    if text is None:
        text = (PROJECT / "integration/chips" / chip / "bond_map.txt").read_text()
    sites = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        site, side, net, instance = line.split()[:4]
        if site in sites:
            raise ValueError(chip + ": site listed twice: " + site)
        sites[site] = dict(side=side, net=net, instance=instance)
    return sites


def chip_families(chip, inventory, bond_map):
    """Pad families present on one chip, with the site of each pin resolved from that chip's bond map.
    A family is present when either of its pins is bonded; then both must be, on neighbouring sites of one side."""
    locations = {}
    for side, ordered in inventory.items():
        for index, site in enumerate(ordered):
            if site in locations:
                raise ValueError("Duplicate provider site: " + site)
            locations[site] = {"side": side, "ordinal": index}
    if set(bond_map) != set(locations):
        raise ValueError(chip + ": bond map sites differ from the provider inventory")
    by_net = {}
    for site, row in bond_map.items():
        if row["net"] in ("VDD", "VSS"):
            continue
        if row["net"] in by_net:
            raise ValueError(chip + ": multiple sites carry " + row["net"])
        by_net[row["net"]] = site
    present = {}
    for family, (block_name, pins, branches) in FAMILIES.items():
        bonded = [pin for pin in pins if pin in by_net]
        if not bonded:
            continue
        if len(bonded) != len(pins):
            raise ValueError(chip + ": " + family + " has only " + ", ".join(bonded) + " bonded")
        pads = [dict(pin=pin, site=by_net[pin], instance=bond_map[by_net[pin]]["instance"], **locations[by_net[pin]])
                for pin in pins]
        if len({p["side"] for p in pads}) != 1 or abs(pads[0]["ordinal"] - pads[1]["ordinal"]) != 1:
            raise ValueError(chip + ": " + family + " pins are not on neighbouring sites of one side")
        if len({p["instance"] for p in pads}) != 1:
            raise ValueError(chip + ": " + family + " pins are on different instances")
        present[family] = pads
    return present


def resolve(architecture=None, contract=None, chip=None, bond_maps=None):
    """Pad family inputs. Sites come from the per-chip bond maps (integration/chips/<chip>/bond_map.txt), never from
    the single-die `candidate_signal_sites` of spec/contract.json. chip=None: every family of either chip, `pads` from
    the first chip that carries it (rf, then wired; the cell geometry is the same on every site pair) and all of them
    in `pads_by_chip`. bond_maps: {chip: bond_map text} to override the files (tests)."""
    if architecture is None:
        architecture = json.loads((PROJECT / "spec/analog-architecture.json").read_text())
    if contract is None:
        contract = json.loads((PROJECT / "spec/contract.json").read_text())
    assembly = contract["assembly_policy"]
    inventory = assembly["provider_site_inventory"]["ordered_sites_by_side"]
    chips = CHIPS if chip is None else (chip,)
    per_chip = {c: chip_families(c, inventory, read_bond_map(c, (bond_maps or {}).get(c))) for c in chips}
    families = {}
    for family, (block_name, pins, branches) in FAMILIES.items():
        carriers = [c for c in chips if family in per_chip[c]]
        if not carriers:
            continue
        block = architecture["blocks"][block_name]
        capacitance = block["parameters"]["capacitance_f_per_leg"]
        if not math.isfinite(capacitance) or capacitance <= 0:
            raise ValueError("Invalid capacitance budget: " + family)
        families[family] = dict(
            block=block_name, pads=per_chip[carriers[0]][family],
            pads_by_chip={c: per_chip[c][family] for c in carriers}, branches=list(branches),
            supply_domain=block["supply"],
            electrical_parameters=block["parameters"],
            capacitance_convention=("odd_mode_effective_per_leg" if family == "wired_receive_usb"
                                    else "per_leg_budget_branch_decomposition_pending"),
            area_ceiling_um2=block["resource_allocation"]["area_ceiling_um2"],
            required_states=list(STATES),
            coverage={state: "pending_integrated_first_pass" for state in STATES},
        )
    return dict(
        status="implementation_inputs_resolved_not_completed_pad_design",
        chips=list(chips),
        families=families,
        retained_library_families=["host_control", "supply_return"],
        provider_inventory=inventory,
        physical_coordinate_status="ordinals_only_requires_provider_placement_geometry",
        assembly_policy=assembly,
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chip", choices=CHIPS, help="one chip; default: both")
    args = parser.parse_args()
    result = resolve(chip=args.chip)
    result["sources_sha256"] = {
        str(p.relative_to(PROJECT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__), PROJECT / "spec/analog-architecture.json", PROJECT / "spec/contract.json",
                  *[PROJECT / "integration/chips" / c / "bond_map.txt" for c in result["chips"]])
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()


def build_integration_candidate(name):
    """Build the shared selected circuit recipe; not an acceptance/publication API.

    Layout composition still adds primary protection, discharge and compensation.
    Delayed imports avoid the circuit/design resolver import cycle.
    """
    spec = json.loads((PROJECT / "spec/schematic-implementation.json").read_text())
    recipes = spec["io_pad_first_pass"]["generation_parameters"]
    if name == "termination_buffer":
        from termination_buffer import build as factory
    elif name == "transmit_interlock":
        from transmit_control_circuit import build as factory
    elif name == "tx_steering_buffer":
        from steering_buffer import build as factory
    elif name == "wired_transmit":
        from circuits import wired_transmit as factory
    elif name == "wired_receive_usb":
        from wired_receive import build as factory
    else:
        raise ValueError("No selected circuit recipe: " + name)
    return factory(**recipes[name])
