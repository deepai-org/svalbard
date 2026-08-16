PYTHON ?= python3
COMPONENT ?= project.pcie_gen1_endpoint
PROJECT ?=

.PHONY: doctor check check-fast check-digital spec process-eligibility scratch-report repo-audit graph smoke bfm-smoke verification-deps-fetch pull

doctor:
	./bootstrap.sh doctor

check: check-fast

check-fast:
	$(PYTHON) scripts/validate.py structure

check-digital: bfm-smoke

spec:
	$(PYTHON) scripts/validate.py spec $(if $(PROJECT),project.$(PROJECT),$(COMPONENT))

process-eligibility:
	$(PYTHON) scripts/validate.py process-eligibility

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

verification-deps-fetch:
	$(PYTHON) scripts/verification_deps.py fetch

bfm-smoke:
	./flows/verification/pcie_bfms/run.sh
