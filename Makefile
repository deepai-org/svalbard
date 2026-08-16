PYTHON ?= python3
COMPONENT ?= project.pcie_gen1_endpoint
PROJECT ?=

.PHONY: doctor check check-fast check-digital spec process-eligibility images-ready toolchain-readiness scratch-report repo-audit graph smoke toolchain-smoke digital-image digital-pnr-smoke bfm-smoke bfm-history-audit verification-deps-fetch tool-artifacts-fetch pull

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

digital-image:
	./env/images/librelane-gf180-canary/build.sh

digital-pnr-smoke: digital-image
	./flows/smoke/digital_pnr/run.sh

verification-deps-fetch:
	$(PYTHON) scripts/verification_deps.py fetch

tool-artifacts-fetch:
	$(PYTHON) scripts/tool_artifacts.py fetch

bfm-smoke:
	./flows/verification/pcie_bfms/run.sh

bfm-history-audit:
	$(PYTHON) scripts/bfm_history_audit.py $(if $(OUTPUT),$(OUTPUT),scratch/bfm-history-audit-last.json)
