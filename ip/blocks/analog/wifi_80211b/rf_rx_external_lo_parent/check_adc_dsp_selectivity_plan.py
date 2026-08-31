#!/usr/bin/env python3
"""Check whether the routed-parent two-tone observation fits the selected ADC/DSP boundary.

This is a deliberately product-specific architecture check.  It does not model
or certify an ADC, a DSP filter, RF linearity, or an 802.11 receiver; it makes
the next required implementation quantitatively explicit from the exact PEX
waveform measurements that precede it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


EXPECTED_ENVIRONMENTS = {
    "tt": ("typical", 3.30, 27),
    "ff_cold": ("ff", 3.63, -40),
    "ff_hot": ("ff", 2.97, 125),
    "ss_hot": ("ss", 2.97, 125),
    "ss_cold": ("ss", 3.63, -40),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def db_ratio(numerator: float, denominator: float) -> float:
    if not (math.isfinite(numerator) and math.isfinite(denominator)
            and numerator > 0.0 and denominator > 0.0):
        return math.nan
    return 20.0 * math.log10(numerator / denominator)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--physical", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text())
    result = json.loads(args.result.read_text())
    physical = json.loads(args.physical.read_text())
    converter = plan["converter_requirements"]
    filter_requirements = plan["digital_filter_requirements"]
    applied = plan["applies_to"]

    require(plan.get("schema_version") == 1
            and plan.get("status") == "architecture_selected_not_implemented"
            and plan.get("selected_path") == "real_if_adc_and_digital_channel_filter",
            "unexpected Wi-Fi selectivity-plan identity")
    require(physical.get("result") == "pass" and physical.get("drc_error_count") == 0
            and physical.get("lvs_unique") is True
            and physical.get("pex_sha256") == digest(args.pex),
            "ADC/DSP boundary lacks physical routed-parent evidence")
    require(result.get("result") == "pass"
            and result.get("claim") == "wifi_2p4g_routed_parent_fixed_two_tone_diagnostic"
            and result.get("pex_sha256") == digest(args.pex),
            "ADC/DSP boundary lacks byte-bound two-tone evidence")
    require(result.get("rf_desired_hz") == applied["rf_desired_hz"]
            and result.get("rf_blocker_hz") == applied["rf_blocker_hz"]
            and result.get("external_lo_hz") == applied["external_lo_hz"]
            and result.get("if_desired_hz") == applied["if_desired_hz"]
            and result.get("if_blocker_hz") == applied["if_blocker_hz"],
            "two-tone frequencies do not match selected ADC/DSP boundary")
    require(converter["minimum_sample_rate_hz"] / 2.0
            > applied["if_blocker_hz"],
            "converter sample rate aliases the observed blocker")
    require(filter_requirements["passband_low_hz"] < applied["if_desired_hz"]
            < filter_requirements["passband_high_hz"]
            < applied["if_blocker_hz"],
            "digital filter does not separate declared desired and blocker tones")

    cases = {case.get("case_id"): case for case in result.get("cases", [])}
    require(set(cases) == set(EXPECTED_ENVIRONMENTS),
            "two-tone PVT environment set changed")
    observations = []
    for name, environment in EXPECTED_ENVIRONMENTS.items():
        case = cases[name]
        require(tuple(case.get("environment", ())) == environment
                and case.get("complete") is True and case.get("result") == "pass",
                f"{name} lacks a complete two-tone observation")
        desired = case["with_blocker"].get("desired_if_peak_v", math.nan)
        blocker = case["with_blocker"].get("blocker_if_peak_v", math.nan)
        input_ratio_db = case.get("blocker_to_desired_if_ratio_db", math.nan)
        require(math.isfinite(desired) and desired > 0.0
                and math.isfinite(blocker) and blocker >= 0.0
                and math.isfinite(input_ratio_db),
                f"{name} has non-finite IF amplitudes")
        full_scale = converter["input_full_scale_peak_v"]
        headroom_limit = full_scale / converter["required_headroom_ratio"]
        quantization_step = 2.0 * full_scale / (2 ** converter["minimum_effective_bits"])
        quantization_noise_rms = quantization_step / math.sqrt(12.0)
        desired_rms = desired / math.sqrt(2.0)
        quantization_snr_db = db_ratio(desired_rms, quantization_noise_rms)
        residual_ratio_db = (input_ratio_db
                             - filter_requirements[
                                 "required_at_blocker_hz_attenuation_db"])
        passed = (blocker <= headroom_limit
                  and quantization_snr_db >= converter[
                      "minimum_quantization_snr_db_for_current_desired_tone"]
                  and residual_ratio_db <= filter_requirements[
                      "maximum_residual_blocker_to_desired_db_for_current_tone"])
        observations.append({
            "case_id": name,
            "desired_if_peak_v": desired,
            "blocker_if_peak_v": blocker,
            "adc_headroom_limit_peak_v": headroom_limit,
            "quantization_snr_db": quantization_snr_db,
            "residual_blocker_to_desired_db_after_required_filter": residual_ratio_db,
            "result": "pass" if passed else "fail",
        })

    output = {
        "schema_version": 1,
        "claim": "wifi_real_if_adc_dsp_selectivity_architecture_boundary",
        "result": "pass" if all(item["result"] == "pass" for item in observations) else "fail",
        "selected_path": plan["selected_path"],
        "verification_level": "byte_bound_pex_input_budget_not_adc_or_dsp_implementation",
        "plan_sha256": digest(args.plan),
        "physical_sha256": digest(args.physical),
        "two_tone_result_sha256": digest(args.result),
        "pex_sha256": digest(args.pex),
        "converter_requirements": converter,
        "digital_filter_requirements": filter_requirements,
        "observations": observations,
        "not_a_claim": plan["not_a_claim"],
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": output["result"],
        "worst_quantization_snr_db": min(item["quantization_snr_db"]
                                           for item in observations),
        "worst_residual_blocker_to_desired_db": max(
            item["residual_blocker_to_desired_db_after_required_filter"]
            for item in observations),
    }, sort_keys=True))
    if output["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
