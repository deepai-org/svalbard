PYTHON ?= python3
COMPONENT ?= project.pcie_gen1_endpoint
PROJECT ?=

.PHONY: doctor check check-fast check-digital spec process-eligibility images-ready toolchain-readiness scratch-report repo-audit graph smoke toolchain-smoke analog-flow-preflight serdes-tx-smoke serdes-termination-smoke serdes-rx-smoke phase-interpolator-smoke cdr-sampler-smoke cdr-phase-detector-smoke cdr-phase-detector-schematic cdr-integrated-detector-schematic cdr-integrated-error-smoke cdr-phase-error-filter-smoke digital-image quaigh-image digital-pnr-smoke bfm-smoke bfm-history-audit verification-deps-fetch tool-artifacts-fetch pull

doctor:
	./bootstrap.sh doctor

check: check-fast

check-fast: smoke
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
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/serdes_tx/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/termination/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/serdes_rx/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/phase_interpolator/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/phase_detector/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/integrated_detector/run.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/integrated_detector/run_composed.sh
	ANALOG_FLOW_CHECK_ONLY=1 ./ip/blocks/analog/wireline_serdes/cdr/phase_error_filter/run.sh

serdes-tx-smoke:
	./ip/blocks/analog/wireline_serdes/serdes_tx/run.sh

serdes-termination-smoke:
	./ip/blocks/analog/wireline_serdes/termination/run.sh

serdes-rx-smoke:
	./ip/blocks/analog/wireline_serdes/serdes_rx/run.sh

phase-interpolator-smoke:
	./ip/blocks/analog/wireline_serdes/phase_interpolator/run.sh

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
