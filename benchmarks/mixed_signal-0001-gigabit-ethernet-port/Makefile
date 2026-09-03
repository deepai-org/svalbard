.PHONY: selftest visible

selftest:
	PYTHONDONTWRITEBYTECODE=1 python3 tests/reference/test_ethernet_oracle.py
	PYTHONDONTWRITEBYTECODE=1 python3 tests/reference/test_codec_8b10b_oracle.py
	PYTHONDONTWRITEBYTECODE=1 python3 tests/reference/test_analog_metrics.py
	PYTHONDONTWRITEBYTECODE=1 python3 tests/coverage/audit_coverage.py
	PYTHONDONTWRITEBYTECODE=1 python3 tests/gating/candidate_safety.py --selftest
	PYTHONDONTWRITEBYTECODE=1 python3 tests/graded/test_result_contract.py
	iverilog -g2012 -s gigabit_ethernet_port -o /tmp/gigabit_ethernet_starter.vvp \
	  environment/input_files/rtl/gigabit_ethernet_port_pkg.sv \
	  environment/input_files/rtl/gigabit_ethernet_port.sv
	@if command -v ngspice >/dev/null 2>&1; then \
	  cd tests/reference && ngspice -b spice_interface_tb.spice >/dev/null; \
	else \
	  echo "ngspice interface self-test: SKIP (ngspice not installed on host)"; \
	fi

visible:
	python3 environment/input_files/test_visible/run_visible.py --output "$${OUTPUT:-/app/output}"
