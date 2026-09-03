.PHONY: selftest visible test

BENCH_ROOT ?= ../..
OUTPUT ?= /app/output

selftest:
	PYTHONDONTWRITEBYTECODE=1 python3 $(BENCH_ROOT)/tests/reference/test_ethernet_oracle.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(BENCH_ROOT)/tests/reference/test_codec_8b10b_oracle.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(BENCH_ROOT)/tests/reference/test_analog_metrics.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(BENCH_ROOT)/tests/coverage/audit_coverage.py
	PYTHONDONTWRITEBYTECODE=1 python3 $(BENCH_ROOT)/tests/graded/test_result_contract.py
	iverilog -g2012 -s gigabit_ethernet_port -o /tmp/gigabit_ethernet_starter.vvp \
	  rtl/gigabit_ethernet_port_pkg.sv rtl/gigabit_ethernet_port.sv

visible:
	python3 test_visible/run_visible.py --output $(OUTPUT)

test: visible
