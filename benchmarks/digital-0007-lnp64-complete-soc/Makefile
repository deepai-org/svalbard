.PHONY: selftest visible pilot

selftest:
	PYTHONDONTWRITEBYTECODE=1 python3 tests/reference/test_boot_image.py
	PYTHONDONTWRITEBYTECODE=1 python3 tests/reference/validate_isa_bundle.py
	PYTHONDONTWRITEBYTECODE=1 python3 tests/reference/validate_platform.py
	PYTHONDONTWRITEBYTECODE=1 python3 tests/reference/test_smp_oracle.py
	PYTHONDONTWRITEBYTECODE=1 python3 tests/gating/run_pcie_adapter.py --oracle-selftest
	PYTHONDONTWRITEBYTECODE=1 python3 tests/reference/audit_standalone.py
	PYTHONDONTWRITEBYTECODE=1 python3 tests/coverage/audit_coverage.py
	PYTHONDONTWRITEBYTECODE=1 python3 tests/graded/test_finalizer.py
	iverilog -g2012 -s lnp64_soc -o /tmp/lnp64_soc_starter.vvp \
		environment/input_files/rtl/lnp64_soc_pkg.sv \
		environment/input_files/rtl/lnp64_soc.sv
	iverilog -g2012 -s tb_lnp64_soc_smoke -o /tmp/lnp64_soc_starter_tb.vvp \
		environment/input_files/rtl/lnp64_soc_pkg.sv \
		environment/input_files/rtl/lnp64_soc.sv \
		environment/input_files/test_visible/tb_lnp64_soc_smoke.sv
	iverilog -g2012 -tnull environment/input_files/memory/lnp64_sram_macros.sv
	iverilog -g2012 -tnull -s tb_jtag_contract \
		environment/input_files/rtl/lnp64_soc_pkg.sv \
		environment/input_files/rtl/lnp64_soc.sv \
		tests/gating/tb_jtag_contract.sv
	PYTHONDONTWRITEBYTECODE=1 python3 tests/gating/run_isa_adapter.py \
		solution/mini_candidate --check-only --include-smp
	PYTHONDONTWRITEBYTECODE=1 python3 tests/physical/check_sram_wrappers.py
	iverilog -g2012 -tnull tests/physical/gf180_sram_functional.sv
	PYTHONDONTWRITEBYTECODE=1 python3 tests/physical/test_gf180_result.py
	PYTHONDONTWRITEBYTECODE=1 python3 tests/physical/run_gf180.py \
		solution/mini_candidate --work /tmp/lnp64-mini-physical --prepare-only
	PYTHONDONTWRITEBYTECODE=1 python3 tests/pilot/run_negative_control.py

visible:
	PYTHONDONTWRITEBYTECODE=1 python3 tests/gating/candidate_safety.py $(OUTPUT)
	OUTPUT=$(OUTPUT) PYTHONDONTWRITEBYTECODE=1 python3 environment/input_files/test_visible/run_visible.py

pilot:
	PYTHONDONTWRITEBYTECODE=1 python3 tests/pilot/run_negative_control.py
