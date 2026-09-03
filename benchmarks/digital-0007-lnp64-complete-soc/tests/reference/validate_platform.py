#!/usr/bin/env python3
import hashlib
import json
import runpy
import tomllib
from pathlib import Path

LOCAL_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = Path("/tests") if Path("/tests/assets").is_dir() else LOCAL_ROOT / "tests"
INPUT = Path("/app/input_files") if Path("/app/input_files/contract").is_dir() else LOCAL_ROOT / "environment/input_files"
CONTRACT = INPUT / "contract"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integer(value: int | str) -> int:
    return int(value, 0) if isinstance(value, str) else value


def main() -> None:
    manifest = json.loads((INPUT / "integration/soc_manifest.json").read_text())
    profile = json.loads((CONTRACT / "soc_profile.json").read_text())
    devices = json.loads((CONTRACT / "platform_devices.json").read_text())
    pdk = json.loads((CONTRACT / "pdk.lock.json").read_text())
    memories = json.loads((INPUT / "memory/sram_macros.json").read_text())
    boot_spec = runpy.run_path(str(INPUT / "spec/boot_image.py"))
    physical = json.loads((TEST_ROOT / "assets/physical_flow.json").read_text())
    reward = json.loads((TEST_ROOT / "assets/tiered_reward.json").read_text())
    coverage = json.loads((TEST_ROOT / "coverage/coverage_manifest.json").read_text())
    adapter = json.loads((TEST_ROOT / "assets/architectural_adapter.json").read_text())
    assert manifest["source_lock_sha256"] == digest(CONTRACT / "source_lock.json")
    assert manifest["soc_profile_sha256"] == digest(CONTRACT / "soc_profile.json")
    assert manifest["platform_devices_sha256"] == digest(CONTRACT / "platform_devices.json")
    assert manifest["pdk_lock_sha256"] == digest(CONTRACT / "pdk.lock.json")
    assert manifest["isa_spec_sha256"] == digest(INPUT / "spec/isa_spec.json")
    assert manifest["boot_spec_sha256"] == digest(INPUT / "spec/boot_image.py")
    assert manifest["sram_contract_sha256"] == digest(INPUT / "memory/sram_macros.json")
    assert profile["machine"] == {"cores": 4, "contexts_per_core": 4, "vlen_bits": 512}
    assert profile["clocks_hz"] == {
        "core": 200000000, "sdram": 100000000,
        "sram_max": 50000000, "pcie_pipe": 125000000,
    }
    assert manifest["cores"] == 4 and manifest["contexts_per_core"] == 4
    assert manifest["vlen_bits"] == 512 and manifest["core_clock_hz"] == 200000000
    assert manifest["sram_clock_max_hz"] == profile["clocks_hz"]["sram_max"]

    ranges = []
    for name, row in profile["memory_map"].items():
        base, size = integer(row["base"]), integer(row["bytes"])
        assert 0 <= base < 1 << 64 and 0 < size <= 1 << 64
        assert base + size <= 1 << 64 and base % 4096 == 0 and size % 4096 == 0
        ranges.append((base, base + size, name))
    for (_, end, left), (start, _, right) in zip(sorted(ranges), sorted(ranges)[1:]):
        assert end <= start, f"memory map overlap: {left}, {right}"

    sdram = profile["sdram"]
    capacity = (1 << sdram["row_bits"]) * (1 << sdram["column_bits"])
    capacity *= sdram["banks"] * sdram["data_bits"] // 8
    assert sdram["physical_capacity_bytes"] == capacity == 1 << 27
    assert sdram["mapped_bytes"] == profile["memory_map"]["sdr_sdram"]["bytes"] == 1 << 26
    assert sdram["byte_address_bits"] == {
        "byte": "1:0", "column": "11:2", "bank": "13:12", "row": "26:14"
    }
    assert (
        sdram["refresh_window_ns"] / sdram["refresh_rows"]
        == sdram["average_refresh_interval_ns"]
    )
    timing = sdram["timing_cycles_100mhz"]
    assert timing["tRC"] >= timing["tRAS"] + timing["tRP"]
    assert timing["max_refresh_gap"] * 10 <= sdram["average_refresh_interval_ns"]
    assert sdram["burst_length"] == 1 and sdram["cas_latency"] == 2
    boot = profile["boot_image"]
    dram_start = integer(profile["memory_map"]["sdr_sdram"]["base"])
    assert integer(boot["payload_load_start"]) == dram_start
    assert integer(boot["payload_load_end_exclusive"]) == dram_start + sdram["mapped_bytes"]
    assert boot["header_bytes"] == 64 and boot["flags_allowed_mask"] == 0
    assert boot_spec["HEADER"].size == boot["header_bytes"]
    assert boot_spec["MAGIC"].decode() == boot["magic_ascii"]
    assert boot_spec["UART_SYNC"].decode() == boot["uart_sync_ascii"]
    assert boot_spec["VERSION"] == boot["version"]
    assert boot_spec["PAGE_BYTES"] == boot["page_bytes"]

    grant = devices["reset_grant"]
    slots = grant["first_domain_cap_slots"]
    assert [row["slot"] for row in slots] == list(range(6))
    assert len({row["slot"] for row in slots}) == len(slots)
    assert slots[2]["class"] == "Device" and slots[2]["profile"] == 4096
    assert {"READ", "WRITE", "EXECUTE/CALL", "MAP"} <= set(slots[4]["rights"])
    assert grant["initial_state"]["r31_sp"] == "0x00020000 for SDHC/UART; 0x0001f000 for JTAG"
    jtag_sram = [row for row in grant["initial_mappings"]
                 if "JTAG" in row["boot_paths"] and row.get("backing_slot") == 4]
    assert jtag_sram == [
        {"base": "0x00000000", "bytes": 4096, "protection": "RW", "backing_slot": 4,
         "backing_offset": 0, "boot_paths": ["JTAG"], "use": "flat-exec zero page"},
        {"base": "0x00001000", "bytes": 8192, "protection": "RWX", "backing_slot": 4,
         "backing_offset": 4096, "boot_paths": ["JTAG"], "use": "flat-exec text loaded by debug"},
        {"base": "0x00010000", "bytes": 4096, "protection": "RW", "backing_slot": 4,
         "backing_offset": 12288, "boot_paths": ["JTAG"], "use": "flat-exec data"},
        {"base": "0x0001e000", "bytes": 4096, "protection": "RW", "backing_slot": 4,
         "backing_offset": 16384, "boot_paths": ["JTAG"], "use": "flat-exec downward-growing stack"},
    ]
    backing_ranges = sorted((row["backing_offset"], row["backing_offset"] + row["bytes"])
                            for row in jtag_sram)
    assert any("X" in row["protection"] for row in jtag_sram)
    assert backing_ranges[-1][1] <= profile["memory_map"]["on_chip_sram"]["bytes"]
    assert all(left[1] <= right[0] for left, right in zip(backing_ranges, backing_ranges[1:]))
    profiles = devices["profiles"]
    assert set(profiles) == {"4096", "4097", "4098", "4099"}
    assert profiles["4096"]["roles"]["1"]["profile"] == 4097
    assert profiles["4096"]["roles"]["2"]["profile"] == 4098
    assert profiles["4096"]["roles"]["3"]["profile"] == 4099
    device_window = profile["memory_map"]["devices"]
    device_start = integer(device_window["base"])
    device_end = device_start + device_window["bytes"]
    bar_ranges = []
    for profile_row in profiles.values():
        for role in profile_row["roles"].values():
            if role.get("name") == "register_bar":
                start, end = map(integer, role["range"])
                assert device_start <= start < end <= device_end
                bar_ranges.append((start, end))
    for (_, end), (start, _) in zip(sorted(bar_ranges), sorted(bar_ranges)[1:]):
        assert end <= start
    assert {integer(row["base"]) for row in devices["registers"].values()} == {
        start for start, _ in bar_ranges
    }
    assert integer(devices["jtag"]["idcode"]) & 1
    assert devices["jtag"]["instructions"]["REGDATA"]["dr_bits"] == 512
    assert devices["jtag"]["instructions"]["MEMDATA"]["dr_bits"] == 64
    assert devices["jtag"]["register_addresses"] == {
        "0x0000-0x001f": "r0-r31, 64 bits",
        "0x0040": "pc, 64 bits",
        "0x0041": "fcsr, 32 bits",
        "0x0042": "stop cause: 0 running, 1 requested halt, 2 architectural exit, 3 unhandled precise fault",
        "0x0043": "architectural exit value, 64 bits; zero unless stop cause is 2",
        "0x0044": "precise fault code, 64 bits; zero unless stop cause is 3",
        "0x0045": "current domain errno, 64 bits",
        "0x0080-0x009f": "f0-f31, 64 bits",
        "0x0100-0x011f": "v0-v31, 512 bits",
        "0x0140-0x014f": "m0-m15, 64 bits",
        "0x0200-0x023f": "PCR selector 0-63, 64 bits",
    }
    mmio = next(row for row in grant["initial_mappings"] if row.get("device_slot") == 2)
    assert mmio == {
        "base": "0x10000000", "bytes": 12288,
        "protection": "RW device_ordered", "device_slot": 2,
        "boot_paths": ["SDHC", "UART", "JTAG"],
        "use": "UART, SDHC, and PCIe register BARs",
    }

    assert profile["pcie"]["pipe_clock_hz"] == profile["clocks_hz"]["pcie_pipe"]
    entropy = profile["entropy"]
    assert entropy["accepted_stream_bits"] == 384
    assert len(entropy["deterministic_test_stream_hex"]) == 96
    assert all(char in "0123456789abcdef" for char in entropy["deterministic_test_stream_hex"])
    assert profile["clocks_hz"]["core"] // profile["clocks_hz"]["sdram"] == 2
    assert profile["clocks_hz"]["core"] // profile["sdhc"]["transfer_clock_hz"] == 8
    assert profile["clocks_hz"]["core"] // profile["sdhc"]["identification_clock_hz"] == 500
    assert profile["status_outputs"]["reserved_boot_error_max_core_cycles"] <= 64
    assert integer(profile["memory_map"]["boot_rom"]["base"]) == 0x1000
    assert integer(profile["memory_map"]["on_chip_sram"]["base"]) == 0x10000
    assert integer(profile["boot_sequence"]["reset_vector"]) == integer(adapter["flat_exec"]["entry"]) == 0x1000
    assert integer(adapter["flat_exec"]["zero_page_base"]) == 0
    assert integer(adapter["flat_exec"]["data_base"]) == 0x10000
    assert integer(adapter["flat_exec"]["stack_base"]) == 0x1e000
    assert adapter["flat_exec"]["stack_bytes"] == 4096
    assert integer(adapter["flat_exec"]["stack_top"]) == 0x1f000
    assert memories["clock_max_hz"] == profile["clocks_hz"]["sram_max"]
    assert memories["clock_max_hz"] <= profile["clocks_hz"]["core"] // 4
    assert memories["clock_max_hz"] == profile["clocks_hz"]["core"] // 4
    assert memories["minimum_core_cycles_per_access"] >= 4
    assert memories["physical_leaf"] == pdk["sram_macro"]["name"]
    assert memories["physical_leaf_corner"] == pdk["sram_macro"]["setup_corner"]
    assert memories["clock_max_hz"] <= pdk["sram_macro"]["clock_max_hz"]
    for row in memories["modules"].values():
        assert row["width"] % 8 == 0 and row["depth"] % 512 == 0
        assert row["leaf_instances"] == row["width"] // 8 * row["depth"] // 512
    assert set(memories["modules"]) == set(manifest["approved_blackboxes"])
    assert set(memories["modules"]) == set(physical["approved_macros"])
    assert physical["flow"] == "LibreLane Classic through OpenROAD.STAPostPNR"
    assert physical["top"] == manifest["top"]
    assert physical["librelane_metrics_corner"] == "nom_" + physical["setup_corner"]
    assert physical["period_ns"] == {"core": 5.0, "pipe": 8.0, "jtag": 40.0}
    assert physical["generated_clocks"] == {"sdram": "core/2", "sd": "core/8"}
    assert physical["eligibility"] == {
        "hierarchy_check": True,
        "inferred_latches": 0,
        "combinational_check": "yosys check -assert",
        "route_drc_errors": 0,
        "setup_wns_min_ns": 0.0,
        "setup_violation_count": 0,
        "mapped_smoke": "reserved boot rejection and JTAG IDCODE/status on the unmodified synthesis-mapped netlist",
    }
    wide = memories["modules"]["lnp64_sram_512x1024_1rw"]
    assert wide["width"] * wide["depth"] // 8 == profile["memory_map"]["on_chip_sram"]["bytes"]

    assert manifest["pdk"] == physical["pdk"] == "GF180MCU/gf180mcuD"
    assert pdk["standard_cell_library"]["name"] == physical["standard_cell_library"]
    assert pdk["standard_cell_library"]["setup_corner"] == physical["setup_corner"]
    image, image_digest = pdk["source_container"].rsplit("@sha256:", 1)
    assert image and len(image_digest) == 64
    assert all(char in "0123456789abcdef" for char in image_digest)
    task_path = LOCAL_ROOT / "task.toml"
    if task_path.is_file():
        task = tomllib.loads(task_path.read_text())
        assert task["environment"]["pdk"] == manifest["pdk"]
        dockerfile = (LOCAL_ROOT / "environment/Dockerfile").read_text()
        assert f"FROM {pdk['source_container']}" in dockerfile
    assert coverage["requirements"] and coverage["scenarios"]
    assert abs(sum(reward["criterion_weights"].values()) - 1.0) < 1e-12
    assert abs(sum(reward["quality_weights"].values()) - 1.0) < 1e-12
    assert set(reward["normalization"]) == set(reward["quality_weights"])
    judge = tomllib.loads((TEST_ROOT / "graded/judge.toml").read_text())["programmatic"]
    normalized = {
        name: weight / sum(judge["weights"])
        for name, weight in zip(("architecture", "physical", "quality"), judge["weights"])
    }
    assert normalized == reward["criterion_weights"]
    print("platform contract: PASS")


if __name__ == "__main__":
    main()
