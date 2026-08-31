PYTHON ?= python3
COMPONENT ?= project.pcie_gen1_endpoint
PROJECT ?=

.PHONY: doctor check check-fast check-digital spec process-eligibility images-ready toolchain-readiness scratch-report repo-audit graph smoke toolchain-smoke analog-flow-preflight serdes-tx-smoke serdes-termination-smoke serdes-rx-smoke wifi-lna-smoke wifi-mixer-smoke wifi-rx-parent-smoke wifi-ostl-coupon-smoke wifi-nfet-array-coupon-smoke phase-interpolator-smoke phase-control-dac-smoke phase-control-integration-smoke cdr-sampler-smoke cdr-phase-detector-smoke cdr-phase-detector-schematic cdr-integrated-detector-schematic cdr-integrated-error-smoke cdr-phase-error-filter-smoke cdr-error-slicer-smoke digital-image quaigh-image digital-pnr-smoke bfm-smoke bfm-history-audit verification-deps-fetch tool-artifacts-fetch pull

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
