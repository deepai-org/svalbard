PYTHON ?= python3
COMPONENT ?= project.pcie_gen1_endpoint
PROJECT ?=

.PHONY: help doctor check check-fast check-digital spec process-eligibility images-ready toolchain-readiness scratch-report repo-audit graph smoke toolchain-smoke analog-flow-preflight serdes-tx-smoke serdes-termination-smoke serdes-rx-smoke wifi-lna-smoke wifi-mixer-smoke wifi-rx-parent-smoke wifi-ostl-coupon-smoke wifi-nfet-array-coupon-smoke phase-interpolator-smoke phase-control-dac-smoke phase-control-integration-smoke cdr-sampler-smoke cdr-phase-detector-smoke cdr-phase-detector-schematic cdr-integrated-detector-schematic cdr-integrated-error-smoke cdr-phase-error-filter-smoke cdr-error-slicer-smoke digital-image quaigh-image digital-pnr-smoke bfm-smoke bfm-history-audit verification-deps-fetch tool-artifacts-fetch pull

help:
	@printf '%s\n' \
	  'SVALBARD common targets:' \
	  '  doctor                  inspect host/tool prerequisites' \
	  '  graph                   validate component dependencies' \
	  '  repo-audit              check tracked-source health budgets' \
	  '  check-fast              run the broad retained fast evidence suite' \
	  '  check-digital           run digital toolchain/PnR/BFM checks' \
	  '  analog-flow-preflight   validate all analog wrapper/container boundaries' \
	  '  scratch-report          report ignored local run storage' \
	  '' \
	  'See README.md and block-local README/run_*.sh files for scoped flows.'

doctor:
	./bootstrap.sh doctor

check: check-fast

check-fast: smoke wifi-lna-smoke wifi-mixer-smoke wifi-rx-parent-smoke wifi-ostl-coupon-smoke wifi-nfet-array-coupon-smoke
	$(PYTHON) scripts/test_analog_evidence.py
	$(PYTHON) scripts/test_analyze_pex_net.py
	$(PYTHON) ip/blocks/analog/wireline_serdes/lane/check_2p5_evidence.py
	$(PYTHON) ip/blocks/analog/wireline_serdes/lane/check_routed_rx_evidence.py
	$(PYTHON) ip/blocks/analog/wireline_serdes/lane/check_rx_frontend_evidence.py
	$(PYTHON) ip/blocks/analog/wireline_serdes/lane/check_rx_capture_evidence.py
	$(PYTHON) ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/check_evidence.py
	$(PYTHON) ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/check_fast_schematic.py --dut ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/cml_to_cmos_fast.spice --result ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/fast_schematic_probe_result.json
	$(PYTHON) ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/check_fast_release.py --physical ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/fast_physical_result.json --timing ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/fast_extracted_result.json --pex ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/cml_to_cmos_fast.pex.spice --render ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/fast_layout.png --layout ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/layout_fast.tcl --layout-core ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/layout.tcl --schematic ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/cml_to_cmos_fast.spice
	$(PYTHON) ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/check_fast_timing_grid.py --current ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/fast_timing_grid_current_result.json --previous ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/fast_timing_grid_previous_result.json
	$(PYTHON) ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/check_fast_checkpoint.py --aggregate ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/fast_capture_pvt_result.json --physical ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/fast_physical_result.json --pex ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/lane_rx_pi_capture_fast.pex.spice --runner ip/blocks/analog/wireline_serdes/lane/run_capture_stress_case.py --merger ip/blocks/analog/wireline_serdes/lane/merge_capture_2p5_calibrated.py --testbench ip/blocks/analog/wireline_serdes/lane/lane_tb.spice.in --render ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/fast_layout.png --top-schematic ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/lane_rx_pi_capture_fast.spice --capture-schematic ip/blocks/analog/wireline_serdes/lane_rx_capture/lane_rx_capture_fast.spice --frontend-schematic ip/blocks/analog/wireline_serdes/lane_rx_frontend/lane_rx_frontend_fast.spice --converter-schematic ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/cml_to_cmos_fast.spice --top-layout ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/layout.tcl --capture-layout ip/blocks/analog/wireline_serdes/lane_rx_capture/layout.tcl --frontend-layout ip/blocks/analog/wireline_serdes/lane_rx_frontend/layout_fast.tcl --frontend-base-layout ip/blocks/analog/wireline_serdes/lane_rx_frontend/layout.tcl --converter-layout ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/layout.tcl --case ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/fast_capture_pvt_tt_result.json --case ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/fast_capture_pvt_ff_cold_result.json --case ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/fast_capture_pvt_ff_hot_result.json --case ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/fast_capture_pvt_ss_hot_result.json --case ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/fast_capture_pvt_ss_passive_result.json
	$(PYTHON) ip/blocks/analog/wireline_serdes/lane_rx_regenerative_capture/check_evidence.py
	$(PYTHON) ip/blocks/analog/wireline_serdes/clock_pulse/check_schematic.py
	$(PYTHON) ip/blocks/analog/wireline_serdes/clock_pulse/check_release.py
	$(PYTHON) ip/blocks/analog/wireline_serdes/clock_pulse/check_pulse_checkpoint.py
	$(PYTHON) scripts/validate.py structure
	$(PYTHON) scripts/validate.py repo-audit

check-digital: toolchain-smoke digital-pnr-smoke bfm-smoke

spec:
	$(PYTHON) scripts/validate.py spec $(if $(PROJECT),project.$(PROJECT),$(COMPONENT))

process-eligibility:
	$(PYTHON) scripts/validate.py process-eligibility

images-ready:
	$(PYTHON) scripts/validate.py image-lock-ready

toolchain-readiness:
	$(PYTHON) scripts/validate.py toolchain-readiness

scratch-report:
	./bootstrap.sh scratch-report

repo-audit:
	$(PYTHON) scripts/validate.py repo-audit

graph:
	$(PYTHON) scripts/validate.py graph

# Pull only the reviewed, digest-pinned ARM64 manifests from env/images.lock.
pull:
	./bootstrap.sh pull

smoke:
	./flows/smoke/run.sh

toolchain-smoke:
	./flows/smoke/digital/run.sh

analog-flow-preflight:
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wifi_80211b/rf_lna/run_lna_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wifi_80211b/rf_switch_mixer/run_mixer_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wifi_80211b/rf_rx_external_lo_parent/run_parent_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wifi_80211b/rf_ostl_coupon/run_coupon_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wifi_80211b/rf_nfet_array_coupon/run_coupon_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/serdes_tx/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/termination/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/serdes_rx/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/serializer/run_schematic.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/serializer/run_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/serializer/run_integrated_tx.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/serializer/run_integrated_tx_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/serializer/run_integrated_tx_2p5_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/deserializer_split/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_stress.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_stress_pvt.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_factor.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_channel_sweep.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_rx_bias_sweep.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_factor_worst.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_bandwidth_mode.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_restorer_sweep.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_restorer_ff_bias.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_restorer_ss_bias.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_extracted_2p5.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_extracted_2p5_pvt.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_precal.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_fast_cal.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_calibrated.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane_rx_spine/run_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_routed_rx.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane_rx_frontend/run_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_rx_frontend.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane_rx_capture/run_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_rx_capture.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/run_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/run_clock_chain.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/run_clock_chain_ss.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane_rx_pi_capture/run_fast_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane_rx_regenerative_frontend/run_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane_rx_regenerative_capture/run_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/clock_pulse/run_level_converter.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/clock_pulse/run_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/clock_pulse/run_bias_scan.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_regenerative_pvt.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_regenerative_ss_aperture.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/run_fast_probe.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/run_fast_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/run_fast_timing_grid.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_rx_pi_smoke.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_rx_pi_screen.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_rx_pi_pvt.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_rx_pi_fast_smoke.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_rx_pi_fast_pvt.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_rx_pi_fast_ss_scan.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_rx_pi_fast_ss_hot_scan.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_rx_pi_fast_ss_phase_scan.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_rx_pi_fast_ss_odd_scan.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_2p5_rx_pi_fast_window_scan.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/lane/run_capture_clock_boundary_compare.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/data_restorer/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/phase_interpolator/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/phase_control_dac/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/phase_control_integration/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/phase_detector/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/integrated_detector/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/integrated_detector/run_composed.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/phase_error_filter/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/error_slicer/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_schematic.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_active_screen.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_cap_drc.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_vco_active_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_guardband_screen.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_guardband_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_vco_bank.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_startup_assist_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_startup_composed.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_selector.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_selector_vco.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_selector_tree_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_selector_tree_gain_screen.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_selector_tree.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_vco_band_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_vco_band.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_vco_band_bank.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_vco_band_gain_screen.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_half_rate_vco_screen.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_half_rate_vco_bank.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_split_control_vco.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_half_rate_vco_full_bank.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_vco_bias_dac.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_vco_bank_top.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_divider_schematic.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_divider_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_clock_restorer_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_clock_restorer_cascade_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_vco_divider_composed.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_vco_divider_clock_screen.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_vco_divider_restorer_screen.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_vco_divider_restorer_full.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_pll_clock_path_physical.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_pll_clock_path_screen.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/pll/run_pll_clock_path_pvt.sh

serdes-tx-smoke:
	./ip/blocks/analog/wireline_serdes/serdes_tx/run.sh

serdes-termination-smoke:
	./ip/blocks/analog/wireline_serdes/termination/run.sh

serdes-rx-smoke:
	./ip/blocks/analog/wireline_serdes/serdes_rx/run.sh

wifi-lna-smoke:
	./ip/blocks/analog/wifi_80211b/rf_lna/run_lna_physical.sh

wifi-mixer-smoke:
	./ip/blocks/analog/wifi_80211b/rf_switch_mixer/run_mixer_physical.sh

wifi-rx-parent-smoke:
	./ip/blocks/analog/wifi_80211b/rf_rx_external_lo_parent/run_parent_physical.sh

wifi-ostl-coupon-smoke:
	./ip/blocks/analog/wifi_80211b/rf_ostl_coupon/run_coupon_physical.sh

wifi-nfet-array-coupon-smoke:
	./ip/blocks/analog/wifi_80211b/rf_nfet_array_coupon/run_coupon_physical.sh

phase-interpolator-smoke:
	./ip/blocks/analog/wireline_serdes/phase_interpolator/run.sh

phase-control-dac-smoke:
	./ip/blocks/analog/wireline_serdes/phase_control_dac/run.sh

phase-control-integration-smoke:
	./ip/blocks/analog/wireline_serdes/phase_control_integration/run.sh

cdr-sampler-smoke:
	./ip/blocks/analog/wireline_serdes/cdr/run.sh

cdr-phase-detector-schematic:
	./ip/blocks/analog/wireline_serdes/cdr/phase_detector/run_schematic.sh

cdr-phase-detector-smoke:
	./ip/blocks/analog/wireline_serdes/cdr/phase_detector/run.sh

cdr-integrated-detector-schematic:
	./ip/blocks/analog/wireline_serdes/cdr/integrated_detector/run.sh

cdr-integrated-error-smoke:
	./ip/blocks/analog/wireline_serdes/cdr/integrated_detector/run_composed.sh

cdr-phase-error-filter-smoke:
	./ip/blocks/analog/wireline_serdes/cdr/phase_error_filter/run.sh

cdr-error-slicer-smoke:
	./ip/blocks/analog/wireline_serdes/cdr/error_slicer/run.sh

digital-image:
	./env/images/librelane-gf180-canary/build.sh

quaigh-image:
	./env/images/quaigh-atpg/build.sh

digital-pnr-smoke: digital-image quaigh-image
	./flows/smoke/digital_pnr/run.sh

verification-deps-fetch:
	$(PYTHON) scripts/verification_deps.py fetch

tool-artifacts-fetch:
	$(PYTHON) scripts/tool_artifacts.py fetch

bfm-smoke:
	./flows/verification/pcie_bfms/run.sh

bfm-history-audit:
	$(PYTHON) scripts/bfm_history_audit.py $(if $(OUTPUT),$(OUTPUT),scratch/bfm-history-audit-last.json)

.PHONY: transceiver-contract
transceiver-contract:
	$(PYTHON) projects/programmable_transceiver_platform/verification/check_contract.py
	$(PYTHON) projects/programmable_transceiver_platform/verification/test_contract.py
	$(PYTHON) projects/programmable_transceiver_platform/verification/test_transport.py
	$(PYTHON) projects/programmable_transceiver_platform/verification/test_frame_codec.py
	$(PYTHON) projects/programmable_transceiver_platform/verification/test_gpio_screen.py
	$(PYTHON) projects/programmable_transceiver_platform/verification/check_power.py
	$(PYTHON) projects/programmable_transceiver_platform/verification/test_power.py

.PHONY: transceiver-gpio-screen
transceiver-gpio-screen:
	bash projects/programmable_transceiver_platform/verification/run_gpio_screen.sh

.PHONY: transceiver-gpio-transient
transceiver-gpio-transient:
	bash projects/programmable_transceiver_platform/verification/run_gpio_transient.sh

.PHONY: transceiver-baseline
transceiver-baseline:
	bash projects/programmable_transceiver_platform/verification/run_baseline.sh

.PHONY: transceiver-synthesis
transceiver-synthesis:
	bash projects/programmable_transceiver_platform/verification/run_synthesis.sh

.PHONY: transceiver-timing-screen
transceiver-timing-screen:
	bash projects/programmable_transceiver_platform/verification/run_timing_screen.sh

.PHONY: transceiver-buffer-screen
transceiver-buffer-screen:
	bash projects/programmable_transceiver_platform/verification/run_buffer_screen.sh

.PHONY: transceiver-clock-power-screen
transceiver-clock-power-screen:
	bash projects/programmable_transceiver_platform/verification/run_clock_power_screen.sh

.PHONY: transceiver-stream-codec
transceiver-stream-codec:
	$(PYTHON) projects/programmable_transceiver_platform/verification/test_stream_codec.py

.PHONY: transceiver-stream-rx
transceiver-stream-rx:
	bash projects/programmable_transceiver_platform/verification/run_stream_rx.sh

.PHONY: transceiver-stream-tx
transceiver-stream-tx:
	bash projects/programmable_transceiver_platform/verification/run_stream_tx.sh

.PHONY: transceiver-stream-link
transceiver-stream-link:
	bash projects/programmable_transceiver_platform/verification/run_stream_link.sh

.PHONY: transceiver-delay-mapping
transceiver-delay-mapping:
	bash projects/programmable_transceiver_platform/verification/run_delay_mapping.sh

.PHONY: transceiver-mapping-equivalence
transceiver-mapping-equivalence:
	bash projects/programmable_transceiver_platform/verification/run_mapping_equivalence.sh

.PHONY: transceiver-placement-screen
transceiver-placement-screen:
	bash projects/programmable_transceiver_platform/verification/run_placement_screen.sh

.PHONY: transceiver-placed-timing
transceiver-placed-timing:
	bash projects/programmable_transceiver_platform/verification/run_placed_timing.sh

.PHONY: transceiver-tx-stage-compare
transceiver-tx-stage-compare:
	bash projects/programmable_transceiver_platform/verification/run_tx_stage_compare.sh

.PHONY: transceiver-pack-stream
transceiver-pack-stream:
	bash projects/programmable_transceiver_platform/verification/run_pack_stream.sh

.PHONY: transceiver-sync-fifo-flags
transceiver-sync-fifo-flags:
	bash projects/programmable_transceiver_platform/verification/run_sync_fifo_flags.sh

.PHONY: transceiver-gray-prefix-proof
transceiver-gray-prefix-proof:
	bash projects/programmable_transceiver_platform/verification/run_gray_prefix.sh

.PHONY: transceiver-current-placement
transceiver-current-placement:
	bash projects/programmable_transceiver_platform/verification/run_current_placement.sh

.PHONY: transceiver-current-repair
transceiver-current-repair:
	bash projects/programmable_transceiver_platform/verification/run_current_repair.sh

.PHONY: transceiver-repaired-geometry
transceiver-repaired-geometry:
	bash projects/programmable_transceiver_platform/verification/run_repaired_geometry.sh

.PHONY: transceiver-pdn-screen
transceiver-pdn-screen:
	bash projects/programmable_transceiver_platform/verification/run_pdn_screen.sh

.PHONY: transceiver-pdn-geometry
transceiver-pdn-geometry:
	bash projects/programmable_transceiver_platform/verification/run_pdn_geometry.sh

.PHONY: transceiver-pdn-ir
transceiver-pdn-ir:
	bash projects/programmable_transceiver_platform/verification/run_pdn_ir.sh

.PHONY: transceiver-pdn-path-bound
transceiver-pdn-path-bound:
	python3 projects/programmable_transceiver_platform/verification/pdn_path_bound.py "$(CURDIR)"

.PHONY: transceiver-wide-pdn
transceiver-wide-pdn:
	bash projects/programmable_transceiver_platform/verification/run_wide_pdn.sh

.PHONY: transceiver-pdn-regional-loads
transceiver-pdn-regional-loads:
	python3 projects/programmable_transceiver_platform/verification/pdn_regional_loads.py "$(CURDIR)"

.PHONY: transceiver-pdn-routing
transceiver-pdn-routing:
	bash projects/programmable_transceiver_platform/verification/run_pdn_routing.sh

.PHONY: transceiver-global-route-timing
transceiver-global-route-timing:
	bash projects/programmable_transceiver_platform/verification/run_global_route_timing.sh

.PHONY: transceiver-block-receiver
transceiver-block-receiver:
	python3 projects/programmable_transceiver_platform/verification/check_block_receiver.py

.PHONY: transceiver-block-fifo
transceiver-block-fifo:
	bash projects/programmable_transceiver_platform/verification/run_block_fifo.sh

.PHONY: transceiver-block-fifo-mapping
transceiver-block-fifo-mapping:
	bash projects/programmable_transceiver_platform/verification/run_block_fifo_mapping.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_fifo_mapping.py

.PHONY: transceiver-block-capture-mapping
transceiver-block-capture-mapping:
	bash projects/programmable_transceiver_platform/verification/run_block_capture_mapping.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_capture.py

.PHONY: transceiver-block-windows
transceiver-block-windows:
	python3 projects/programmable_transceiver_platform/verification/check_block_windows.py

.PHONY: transceiver-block-capture-hold
transceiver-block-capture-hold:
	bash projects/programmable_transceiver_platform/verification/run_block_capture_hold.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_capture_hold.py

.PHONY: transceiver-block-capture-corners
transceiver-block-capture-corners:
	bash projects/programmable_transceiver_platform/verification/run_block_capture_corners.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_capture_corners.py

.PHONY: transceiver-block-capture-placement
transceiver-block-capture-placement:
	bash projects/programmable_transceiver_platform/verification/run_block_capture_placement.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_capture_placement.py

.PHONY: transceiver-block-capture-cts
transceiver-block-capture-cts:
	bash projects/programmable_transceiver_platform/verification/run_block_capture_cts.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_capture_cts.py

.PHONY: transceiver-block-elastic
transceiver-block-elastic:
	bash projects/programmable_transceiver_platform/verification/run_block_elastic.sh

.PHONY: transceiver-block-elastic-mapping
transceiver-block-elastic-mapping:
	bash projects/programmable_transceiver_platform/verification/run_block_elastic_mapping.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_elastic_mapping.py

.PHONY: transceiver-block-elastic-physical
transceiver-block-elastic-physical:
	bash projects/programmable_transceiver_platform/verification/run_block_elastic_physical.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_elastic_physical.py

.PHONY: transceiver-block-elastic-boundary
transceiver-block-elastic-boundary:
	bash projects/programmable_transceiver_platform/verification/run_block_elastic_boundary.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_elastic_boundary.py

.PHONY: transceiver-block-staged
transceiver-block-staged:
	bash projects/programmable_transceiver_platform/verification/run_block_staged.sh

.PHONY: transceiver-lane-compact
transceiver-lane-compact:
	bash projects/programmable_transceiver_platform/verification/run_lane_compact.sh

.PHONY: transceiver-block-route
transceiver-block-route:
	bash projects/programmable_transceiver_platform/verification/run_block_route.sh

.PHONY: transceiver-block-header
transceiver-block-header:
	bash projects/programmable_transceiver_platform/verification/run_block_header.sh

.PHONY: transceiver-block-rx
transceiver-block-rx:
	bash projects/programmable_transceiver_platform/verification/run_block_rx.sh

.PHONY: transceiver-block-rx-mapping
transceiver-block-rx-mapping:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_mapping.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_rx_mapping.py

.PHONY: transceiver-block-rx-pipe
transceiver-block-rx-pipe:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_pipe.sh

.PHONY: transceiver-block-rx-pipe-mapping
transceiver-block-rx-pipe-mapping:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_pipe_mapping.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_rx_pipe_mapping.py

.PHONY: transceiver-block-rx-mask
transceiver-block-rx-mask:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_mask.sh

.PHONY: transceiver-block-rx-mask-mapping
transceiver-block-rx-mask-mapping:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_mask_mapping.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_rx_mask_mapping.py

.PHONY: transceiver-route-rank transceiver-block-rx-rank
transceiver-route-rank:
	bash projects/programmable_transceiver_platform/verification/run_route_rank.sh
transceiver-block-rx-rank:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_rank.sh

.PHONY: transceiver-block-rx-rank-mapping
transceiver-block-rx-rank-mapping:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_rank_mapping.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_rx_rank_mapping.py

.PHONY: transceiver-route-prefix transceiver-block-rx-prefix
transceiver-route-prefix:
	bash projects/programmable_transceiver_platform/verification/run_route_prefix.sh
transceiver-block-rx-prefix:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_prefix.sh

.PHONY: transceiver-block-rx-prefix-mapping
transceiver-block-rx-prefix-mapping:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_prefix_mapping.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_rx_prefix_mapping.py

.PHONY: transceiver-block-rx-prefix-corners
transceiver-block-rx-prefix-corners:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_prefix_corners.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_rx_prefix_corners.py

.PHONY: transceiver-block-rx-commit
transceiver-block-rx-commit:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_commit.sh

.PHONY: transceiver-block-rx-commit-mapping transceiver-block-rx-commit-corners
transceiver-block-rx-commit-mapping:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_commit_mapping.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_rx_commit_mapping.py
transceiver-block-rx-commit-corners:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_commit_corners.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_rx_commit_corners.py

.PHONY: transceiver-block-rx-commit-physical
transceiver-block-rx-commit-physical:
	bash projects/programmable_transceiver_platform/verification/run_block_rx_commit_physical.sh
	python3 projects/programmable_transceiver_platform/verification/report_block_rx_commit_physical.py

.PHONY: transceiver-compact-rank
transceiver-compact-rank:
	bash projects/programmable_transceiver_platform/verification/run_compact_rank.sh

.PHONY: transceiver-lna-load
transceiver-lna-load:
	bash projects/programmable_transceiver_platform/verification/run_lna_load_screen.sh

.PHONY: transceiver-lna-mixer
transceiver-lna-mixer:
	python3 projects/programmable_transceiver_platform/verification/check_rf_projection.py
	bash projects/programmable_transceiver_platform/verification/run_lna_mixer_screen.sh

.PHONY: transceiver-rx-iq
transceiver-rx-iq:
	bash projects/programmable_transceiver_platform/verification/run_rx_iq_screen.sh

.PHONY: transceiver-rx-branch-load
transceiver-rx-branch-load:
	bash projects/programmable_transceiver_platform/verification/run_rx_branch_load_screen.sh

.PHONY: transceiver-rx-split
transceiver-rx-split:
	bash projects/programmable_transceiver_platform/verification/run_rx_split_screen.sh

.PHONY: transceiver-rx-phase
transceiver-rx-phase:
	bash projects/programmable_transceiver_platform/verification/run_rx_phase_screen.sh

.PHONY: transceiver-lo-buffer
transceiver-lo-buffer:
	python3 projects/programmable_transceiver_platform/verification/check_lo_measurement.py
	bash projects/programmable_transceiver_platform/verification/run_lo_buffer_screen.sh

.PHONY: transceiver-rx-buffered
transceiver-rx-buffered:
	bash projects/programmable_transceiver_platform/verification/run_rx_buffered_screen.sh

.PHONY: transceiver-rx-process
transceiver-rx-process:
	bash projects/programmable_transceiver_platform/verification/run_rx_process_screen.sh

.PHONY: transceiver-rx-mixed-process
transceiver-rx-mixed-process:
	bash projects/programmable_transceiver_platform/verification/run_rx_mixed_process_screen.sh

.PHONY: transceiver-rx-sampler
transceiver-rx-sampler:
	bash projects/programmable_transceiver_platform/verification/run_rx_sampler_screen.sh

.PHONY: transceiver-rx-filtered-sampler
transceiver-rx-filtered-sampler:
	bash projects/programmable_transceiver_platform/verification/run_rx_filtered_sampler_screen.sh

.PHONY: transceiver-rx-filtered-settling
transceiver-rx-filtered-settling:
	bash projects/programmable_transceiver_platform/verification/run_rx_filtered_settling.sh

.PHONY: transceiver-rx-alias
transceiver-rx-alias:
	bash projects/programmable_transceiver_platform/verification/run_rx_alias_screen.sh

.PHONY: transceiver-bb-gain
transceiver-bb-gain:
	bash projects/programmable_transceiver_platform/verification/run_bb_gain_screen.sh

.PHONY: transceiver-bb-swing
transceiver-bb-swing:
	bash projects/programmable_transceiver_platform/verification/run_bb_swing_screen.sh

.PHONY: transceiver-bb-pmos-gain transceiver-bb-pmos-swing transceiver-bb-pmos-cascade
transceiver-bb-pmos-gain:
	bash projects/programmable_transceiver_platform/verification/run_bb_pmos_gain_screen.sh
transceiver-bb-pmos-swing:
	bash projects/programmable_transceiver_platform/verification/run_bb_pmos_swing_screen.sh
transceiver-bb-pmos-cascade:
	bash projects/programmable_transceiver_platform/verification/run_bb_pmos_cascade_screen.sh

.PHONY: transceiver-bb-filter
transceiver-bb-filter:
	bash projects/programmable_transceiver_platform/verification/run_bb_filter_screen.sh

.PHONY: transceiver-rf-vco-load
transceiver-rf-vco-load:
	bash projects/programmable_transceiver_platform/verification/run_rf_vco_load_screen.sh

.PHONY: transceiver-wired-pulse-data
transceiver-wired-pulse-data:
	./projects/programmable_transceiver_platform/verification/run_wired_pulse_data_screen.sh

.PHONY: transceiver-wired-phase
transceiver-wired-phase:
	./projects/programmable_transceiver_platform/verification/run_wired_phase_screen.sh

.PHONY: transceiver-wired-internal
transceiver-wired-internal:
	./projects/programmable_transceiver_platform/verification/run_wired_internal_screen.sh

.PHONY: transceiver-wired-boost-off
transceiver-wired-boost-off:
	./projects/programmable_transceiver_platform/verification/run_wired_boost_off_screen.sh

.PHONY: transceiver-wired-frozen-pattern
transceiver-wired-frozen-pattern:
	./projects/programmable_transceiver_platform/verification/run_wired_frozen_pattern_screen.sh

.PHONY: transceiver-model-behavior transceiver-lna-noise-feasibility
transceiver-model-behavior:
	bash projects/programmable_transceiver_platform/verification/run_model_behavior_screen.sh
	python3 projects/programmable_transceiver_platform/verification/check_model_behavior.py

transceiver-lna-noise-feasibility:
	bash projects/programmable_transceiver_platform/verification/run_lna_noise_feasibility.sh

.PHONY: transceiver-rf-ac-clock transceiver-rf-autonomous-chain transceiver-rf-supply-ripple
transceiver-rf-ac-clock:
	bash projects/programmable_transceiver_platform/verification/run_rf_ac_clock_screen.sh

transceiver-rf-autonomous-chain:
	bash projects/programmable_transceiver_platform/verification/run_rf_autonomous_chain_screen.sh
	python3 projects/programmable_transceiver_platform/verification/analyze_rf_autonomous_chain.py

transceiver-rf-supply-ripple:
	bash projects/programmable_transceiver_platform/verification/run_rf_supply_ripple_screen.sh
	bash projects/programmable_transceiver_platform/verification/run_rf_supply_ripple_screen.sh 0.5 -fine
	python3 projects/programmable_transceiver_platform/verification/analyze_rf_supply_ripple.py

.PHONY: transceiver-rf-lo-controls
transceiver-rf-lo-controls:
	bash projects/programmable_transceiver_platform/verification/run_rf_ideal_lo_control.sh
	bash projects/programmable_transceiver_platform/verification/run_rf_ideal_lo_control.sh -limited --limited-swing
	python3 projects/programmable_transceiver_platform/verification/analyze_rf_lo_controls.py

.PHONY: transceiver-rf-loading-op
transceiver-rf-loading-op:
	bash projects/programmable_transceiver_platform/verification/run_rf_loading_op_screen.sh

.PHONY: transceiver-rf-if-cap
transceiver-rf-if-cap:
	bash projects/programmable_transceiver_platform/verification/run_rf_ideal_lo_control.sh -cap01 '--if-cap-pf 0.1'
	python3 projects/programmable_transceiver_platform/verification/analyze_rf_if_cap.py

.PHONY: transceiver-rf-candidate-bias transceiver-rf-prebias
transceiver-rf-candidate-bias:
	bash projects/programmable_transceiver_platform/verification/run_rf_candidate_bias.sh
	python3 projects/programmable_transceiver_platform/verification/check_rf_candidate_bias.py

transceiver-rf-prebias:
	bash projects/programmable_transceiver_platform/verification/run_rf_ideal_lo_control.sh -prebias --prebias
	python3 projects/programmable_transceiver_platform/verification/analyze_rf_prebias.py

.PHONY: transceiver-rf-bias-startup
transceiver-rf-bias-startup:
	bash projects/programmable_transceiver_platform/verification/run_rf_bias_startup.sh
	python3 projects/programmable_transceiver_platform/verification/check_rf_bias_startup.py

.PHONY: transceiver-schematic-inventory
transceiver-schematic-inventory:
	python3 projects/programmable_transceiver_platform/verification/audit_schematic_inventory.py

.PHONY: transceiver-pll-pfd
transceiver-pll-pfd:
	bash projects/programmable_transceiver_platform/verification/run_pll_pfd.sh
	python3 projects/programmable_transceiver_platform/verification/check_pll_pfd.py

.PHONY: transceiver-pll-pfd-frequency
transceiver-pll-pfd-frequency:
	bash projects/programmable_transceiver_platform/verification/run_pll_pfd_frequency.sh
	python3 projects/programmable_transceiver_platform/verification/check_pll_pfd_frequency.py

.PHONY: transceiver-pll-charge-pump
transceiver-pll-charge-pump:
	bash projects/programmable_transceiver_platform/verification/run_pll_charge_pump.sh
	python3 projects/programmable_transceiver_platform/verification/check_pll_charge_pump.py

.PHONY: transceiver-pll-pfd-pump
transceiver-pll-pfd-pump:
	bash projects/programmable_transceiver_platform/verification/run_pll_pfd_pump.sh
	python3 projects/programmable_transceiver_platform/verification/check_pll_pfd_pump.py

.PHONY: transceiver-pll-filter
transceiver-pll-filter:
	bash projects/programmable_transceiver_platform/verification/run_pll_filter.sh
	python3 projects/programmable_transceiver_platform/verification/check_pll_filter.py

.PHONY: transceiver-vco-local-tuning
transceiver-vco-local-tuning:
	bash projects/programmable_transceiver_platform/verification/run_vco_local_tuning.sh
	python3 projects/programmable_transceiver_platform/verification/check_vco_local_tuning.py

.PHONY: transceiver-loaded-divider
transceiver-loaded-divider:
	bash projects/programmable_transceiver_platform/verification/run_loaded_divider.sh
	python3 projects/programmable_transceiver_platform/verification/check_loaded_divider.py

.PHONY: transceiver-divider-chain
transceiver-divider-chain:
	bash projects/programmable_transceiver_platform/verification/run_divider_chain.sh
	python3 projects/programmable_transceiver_platform/verification/check_divider_chain.py

.PHONY: transceiver-closed-loop
transceiver-closed-loop:
	bash projects/programmable_transceiver_platform/verification/run_closed_loop.sh
	python3 projects/programmable_transceiver_platform/verification/check_closed_loop.py

.PHONY: transceiver-vco-capture-tuning
transceiver-vco-capture-tuning:
	bash projects/programmable_transceiver_platform/verification/run_vco_capture_tuning.sh
	python3 projects/programmable_transceiver_platform/verification/check_vco_capture_tuning.py

.PHONY: transceiver-vco-split-tuning
transceiver-vco-split-tuning:
	bash projects/programmable_transceiver_platform/verification/run_vco_split_tuning.sh
	python3 projects/programmable_transceiver_platform/verification/check_vco_split_tuning.py

.PHONY: transceiver-vco-split-lower
transceiver-vco-split-lower:
	bash projects/programmable_transceiver_platform/verification/run_vco_split_lower.sh
	python3 projects/programmable_transceiver_platform/verification/check_vco_split_lower.py

.PHONY: transceiver-closed-loop-split
transceiver-closed-loop-split:
	bash projects/programmable_transceiver_platform/verification/run_closed_loop_split.sh
	python3 projects/programmable_transceiver_platform/verification/check_closed_loop_split.py
	python3 projects/programmable_transceiver_platform/verification/pll_split_response.py

.PHONY: transceiver-closed-loop-extended
transceiver-closed-loop-extended:
	bash projects/programmable_transceiver_platform/verification/run_closed_loop_extended.sh
	python3 projects/programmable_transceiver_platform/verification/check_closed_loop_extended.py

.PHONY: transceiver-adc-comparator
transceiver-adc-comparator:
	bash projects/programmable_transceiver_platform/verification/run_adc_comparator.sh
	python3 projects/programmable_transceiver_platform/verification/check_adc_comparator.py

.PHONY: transceiver-adc-sampled-comparator
transceiver-adc-sampled-comparator:
	bash projects/programmable_transceiver_platform/verification/run_sampled_comparator.sh
	python3 projects/programmable_transceiver_platform/verification/check_sampled_comparator.py

.PHONY: transceiver-adc-cdac-step
transceiver-adc-cdac-step:
	bash projects/programmable_transceiver_platform/verification/run_cdac_step.sh
	python3 projects/programmable_transceiver_platform/verification/check_cdac_step.py

.PHONY: transceiver-adc-cdac-scaled
transceiver-adc-cdac-scaled:
	bash projects/programmable_transceiver_platform/verification/run_cdac_scaled.sh
	python3 projects/programmable_transceiver_platform/verification/check_cdac_step.py --scaled

.PHONY: transceiver-adc-cdac-reference
transceiver-adc-cdac-reference:
	bash projects/programmable_transceiver_platform/verification/run_cdac_reference.sh
	python3 projects/programmable_transceiver_platform/verification/check_cdac_reference.py

.PHONY: transceiver-closed-loop-settling
transceiver-closed-loop-settling:
	bash projects/programmable_transceiver_platform/verification/run_closed_loop_settling.sh
	python3 projects/programmable_transceiver_platform/verification/check_closed_loop_extended.py --settling

.PHONY: transceiver-adc-cdac-driver
transceiver-adc-cdac-driver:
	bash projects/programmable_transceiver_platform/verification/run_cdac_driver.sh
	python3 projects/programmable_transceiver_platform/verification/check_cdac_driver.py

.PHONY: transceiver-adc-cdac-small-driver
transceiver-adc-cdac-small-driver:
	bash projects/programmable_transceiver_platform/verification/run_cdac_small_driver.sh
	python3 projects/programmable_transceiver_platform/verification/check_cdac_driver.py --small

.PHONY: transceiver-adc-cdac-supply
transceiver-adc-cdac-supply:
	bash projects/programmable_transceiver_platform/verification/run_cdac_supply.sh
	python3 projects/programmable_transceiver_platform/verification/check_cdac_supply.py

.PHONY: transceiver-adc-sar8-closed
transceiver-adc-sar8-closed:
	bash projects/programmable_transceiver_platform/verification/run_sar8_closed.sh
	python3 projects/programmable_transceiver_platform/verification/check_sar8_closed.py

.PHONY: transceiver-adc-sar8-buffered
transceiver-adc-sar8-buffered:
	bash projects/programmable_transceiver_platform/verification/run_sar8_buffered.sh
	python3 projects/programmable_transceiver_platform/verification/check_sar8_closed.py --buffered

.PHONY: transceiver-adc-sar8-fast
transceiver-adc-sar8-fast:
	bash projects/programmable_transceiver_platform/verification/run_sar8_fast.sh
	python3 projects/programmable_transceiver_platform/verification/check_sar8_closed.py --fast

.PHONY: transceiver-adc-sar-acquisition
transceiver-adc-sar-acquisition:
	bash projects/programmable_transceiver_platform/verification/run_sar_acquisition.sh
	python3 projects/programmable_transceiver_platform/verification/check_sar_acquisition.py

.PHONY: transceiver-adc-sample-driver
transceiver-adc-sample-driver:
	bash projects/programmable_transceiver_platform/verification/run_sample_driver.sh
	python3 projects/programmable_transceiver_platform/verification/check_sample_driver.py

.PHONY: transceiver-adc-sample-driver-longmirror
transceiver-adc-sample-driver-longmirror:
	bash projects/programmable_transceiver_platform/verification/run_sample_driver_longmirror.sh
	python3 projects/programmable_transceiver_platform/verification/check_sample_driver.py --longmirror

.PHONY: transceiver-adc-sample-driver-op
transceiver-adc-sample-driver-op:
	bash projects/programmable_transceiver_platform/verification/run_sample_driver_op.sh
	python3 projects/programmable_transceiver_platform/verification/check_sample_driver_op.py

.PHONY: transceiver-adc-sample-driver-headroom-op
transceiver-adc-sample-driver-headroom-op:
	bash projects/programmable_transceiver_platform/verification/run_sample_driver_headroom_op.sh
	python3 projects/programmable_transceiver_platform/verification/check_sample_driver_op.py --headroom

.PHONY: transceiver-adc-sample-driver-headroom
transceiver-adc-sample-driver-headroom:
	bash projects/programmable_transceiver_platform/verification/run_sample_driver_headroom.sh
	python3 projects/programmable_transceiver_platform/verification/check_sample_driver.py --headroom

.PHONY: transceiver-adc-sar8-driven
transceiver-adc-sar8-driven:
	bash projects/programmable_transceiver_platform/verification/run_sar8_driven.sh
	python3 projects/programmable_transceiver_platform/verification/check_sar8_driven.py

.PHONY: transceiver-adc-sar8-frames
transceiver-adc-sar8-frames:
	bash projects/programmable_transceiver_platform/verification/run_sar8_frames.sh
	python3 projects/programmable_transceiver_platform/verification/check_sar8_frames.py

.PHONY: transceiver-adc-sar8-masked-frames
transceiver-adc-sar8-masked-frames:
	bash projects/programmable_transceiver_platform/verification/run_sar8_masked_frames.sh
	python3 projects/programmable_transceiver_platform/verification/check_sar8_frames.py --masked

.PHONY: transceiver-adc-sar8-early-mask-frames
transceiver-adc-sar8-early-mask-frames:
	bash projects/programmable_transceiver_platform/verification/run_sar8_early_mask_frames.sh
	python3 projects/programmable_transceiver_platform/verification/check_sar8_frames.py --early

.PHONY: transceiver-adc-sar8-strong-mask-frames transceiver-adc-mim-model transceiver-adc-sar8-mim-frames
transceiver-adc-sar8-strong-mask-frames:
	bash projects/programmable_transceiver_platform/verification/run_sar8_strong_mask_frames.sh
	python3 projects/programmable_transceiver_platform/verification/check_sar8_frames.py --strong

transceiver-adc-mim-model:
	bash projects/programmable_transceiver_platform/verification/run_mim_model.sh
	python3 projects/programmable_transceiver_platform/verification/check_mim_model.py

transceiver-adc-sar8-mim-frames:
	bash projects/programmable_transceiver_platform/verification/run_sar8_mim_frames.sh
	python3 projects/programmable_transceiver_platform/verification/check_sar8_mim_frames.py --require-complete

.PHONY: transceiver-adc-reference-driver
transceiver-adc-reference-driver:
	bash projects/programmable_transceiver_platform/verification/run_sar8_reference_driver.sh
	python3 projects/programmable_transceiver_platform/verification/check_sar8_mim_frames.py --reference-driver --require-complete

.PHONY: transceiver-current-dac-dc
transceiver-current-dac-dc:
	bash projects/programmable_transceiver_platform/verification/run_current_dac_dc.sh
	python3 projects/programmable_transceiver_platform/verification/check_current_dac_dc.py

.PHONY: transceiver-behavioral
transceiver-behavioral:
	$(PYTHON) projects/programmable_transceiver_platform/system_model/architecture_fast/behavioral.py

.PHONY: transceiver-math-fast
transceiver-math-fast:
	OPENBLAS_NUM_THREADS=1 python3 projects/programmable_transceiver_platform/system_model/architecture_fast/acceptance.py

.PHONY: transceiver-protocol-model transceiver-protocol-coupled
transceiver-protocol-model:
	OPENBLAS_NUM_THREADS=1 $(PYTHON) projects/programmable_transceiver_platform/verification/protocol_model_check.py

transceiver-protocol-coupled:
	OPENBLAS_NUM_THREADS=1 $(PYTHON) projects/programmable_transceiver_platform/verification/protocol_model_check.py --coupled
