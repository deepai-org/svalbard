#!/usr/bin/env python3
"""Reconcile area ledgers without booking reserve or claiming placement fit."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]


def report(output):
    architecture_path = PROJECT/'spec/analog-architecture.json'
    readiness_path = PROJECT/'spec/tapeout-readiness.json'
    hardening_path = PROJECT/'evidence/digital-hardening-evidence.json'
    control_path = PROJECT/'analog/bringup_control/generated/lef-evidence.json'
    architecture = json.loads(architecture_path.read_text())
    readiness = json.loads(readiness_path.read_text())
    hardening = json.loads(hardening_path.read_text())
    control = json.loads(control_path.read_text())
    groups = defaultdict(int)
    for block in architecture['blocks'].values():
        allocation = block['resource_allocation']
        groups[allocation['area_group']] += allocation['area_ceiling_um2']
    assert dict(groups) == architecture['resource_totals']['area_used_um2']
    budgets = architecture['area_budget_um2']
    # Memory is a separate architecture reservation, implemented inside the
    # hardened digital macro. Replace BOTH reservations with its full bbox.
    total = sum(budgets.values())
    memory = architecture['resource_policy']['memory_area_ceiling_um2']
    assert memory == budgets['memory']
    slack = total-sum(groups.values())-memory
    freed = architecture['freed_area_allocation_um2']
    assert slack == freed['total_slack'] == sum(freed['allocations'].values())
    reserve = readiness['reserve_area_mm2']
    allocated = {k: round(v*1e6) for k, v in reserve['allocated'].items()}
    debug = allocated['debug_cells_measured']+allocated['debug_cells_planned_remaining']
    assert debug == freed['allocations']['debug']
    physical = hardening['physical']
    digital = physical['die_area_um2']
    assert physical['allocation_um2']['total'] == budgets['digital']+memory
    assert control['status'] == 'pass'
    x0,y0,x1,y1 = control['gds_bbox_um']
    control_area = (x1-x0)*(y1-y0)
    # These are existing planning ceilings, not new measured geometry. Keep
    # them and power/decap fully charged. Do not deduct debug a second time
    # from freed.allocations.reserve, which already excludes it.
    charges = dict(
        non_digital_block_ceilings=sum(groups.values())-groups['digital'],
        historical_hardened_digital_bbox=digital,
        debug_cells=debug,
        debug_site_protection=allocated['debug_site_protection_planned'],
        atb_tree=allocated['atb_tree'],
        additional_bringup_control_bbox=control_area)
    remaining = total-sum(charges.values())
    changed = [name for name, digest in hardening['source_hashes'].items()
               if (PROJECT/name).exists() and
               hashlib.sha256((PROJECT/name).read_bytes()).hexdigest() != digest.removeprefix('sha256:')]
    data = dict(
        status='planning_reconciliation_not_placement_signoff',
        total_group_budget_um2=total, block_ceilings_by_group_um2=dict(groups),
        separate_memory_reservation_um2=memory,
        architecture_slack_before_debug_um2=slack,
        architecture_reserve_after_debug_um2=freed['allocations']['reserve'],
        readiness_declared_available_um2=round(reserve['available']*1e6),
        readiness_available_minus_architecture_reserve_um2=round(reserve['available']*1e6)-freed['allocations']['reserve'],
        readiness_standalone_remaining_um2=round(reserve['available']*1e6)-sum(allocated.values()),
        digital_bbox_over_combined_allocation_um2=digital-budgets['digital']-memory,
        digital_bbox_over_booked_digital_and_memory_um2=digital-groups['digital']-memory,
        reconciled_charges_um2=charges,
        conditional_unassigned_area_um2=remaining,
        historical_hardening_changed_inputs=changed,
        assumptions=[
            'The historical digital macro replaces digital block ceilings and the separate memory reservation; memory is not charged twice.',
            'Architecture debug allocation and readiness measured/planned debug entries describe the same 670000 um2.',
            'The 1300000 um2 power/decap ceiling remains in non-digital blocks.',
            'Bringup control is conservatively additional until its owner books it within a block ceiling.',
            'Other block ceilings remain planning reservations; bounding boxes, routing and separation can exceed them.'],
        remaining_work=[
            'Reconcile readiness reserve availability with the architecture ledger and document whether available is before or after debug.',
            'Book the digital overrun and control ownership explicitly after choosing the physical digital implementation.',
            'Re-harden changed RTL and substitute its actual final bounds.',
            'Prove placement/routing, power straps, protection buses and 1 nF decap fit in the provider core.'],
        source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                       [Path(__file__).resolve(), architecture_path, readiness_path, hardening_path, control_path]})
    output.mkdir(parents=True, exist_ok=True)
    (output/'report.json').write_text(json.dumps(data, indent=2)+'\n')
    print(json.dumps({k: data[k] for k in ['status', 'digital_bbox_over_combined_allocation_um2',
        'readiness_available_minus_architecture_reserve_um2', 'conditional_unassigned_area_um2',
        'historical_hardening_changed_inputs']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/area-budget')
    report(parser.parse_args().output_dir.resolve())
