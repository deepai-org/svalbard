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


def resolve(architecture=None, contract=None):
    if architecture is None:
        architecture = json.loads((PROJECT / "spec/analog-architecture.json").read_text())
    if contract is None:
        contract = json.loads((PROJECT / "spec/contract.json").read_text())
    assembly = contract["assembly_policy"]
    sites = assembly["candidate_signal_sites"]
    inventory = assembly["provider_site_inventory"]["ordered_sites_by_side"]
    locations = {}
    for side, ordered in inventory.items():
        for index, site in enumerate(ordered):
            if site in locations:
                raise ValueError("Duplicate provider site: " + site)
            locations[site] = {"side": side, "ordinal": index}
    if len(set(sites.values())) != len(sites):
        raise ValueError("Multiple signals assigned to one physical site")
    families = {}
    for family, (block_name, pins, branches) in FAMILIES.items():
        block = architecture["blocks"][block_name]
        capacitance = block["parameters"]["capacitance_f_per_leg"]
        if not math.isfinite(capacitance) or capacitance <= 0:
            raise ValueError("Invalid capacitance budget: " + family)
        pads = []
        for pin in pins:
            site = sites[pin]
            if site not in locations:
                raise ValueError("Signal has no provider site: " + pin)
            pads.append(dict(pin=pin, site=site, **locations[site]))
        families[family] = dict(
            block=block_name, pads=pads, branches=list(branches),
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
    args = parser.parse_args()
    result = resolve()
    result["sources_sha256"] = {
        str(p.relative_to(PROJECT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__), PROJECT / "spec/analog-architecture.json", PROJECT / "spec/contract.json")
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
