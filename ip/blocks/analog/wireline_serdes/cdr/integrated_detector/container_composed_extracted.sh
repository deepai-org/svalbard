#!/usr/bin/env bash
set -euo pipefail

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/sampler-layout.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cdr_sampler_pex -w /work/sampler-pex \
  /work/cdr_sampler.mag > /work/sampler-pex.log 2>&1

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/phase_detector/layout.tcl > /work/detector-layout.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_alexander_boundary_pex -w /work/detector-pex \
  /work/cml_alexander_boundary.mag > /work/detector-pex.log 2>&1

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/phase_error_filter/layout.tcl > /work/error-layout.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_phase_error_filter_pex -w /work/error-pex \
  /work/cml_phase_error_filter.mag > /work/error-pex.log 2>&1

sampler=/work/sampler-pex/cdr_sampler.pex.spice
detector=/work/detector-pex/cml_alexander_boundary.pex.spice
error=/work/error-pex/cml_phase_error_filter.pex.spice
python3 /src/integrated_detector/run_composed_error.py --source /src \
  --calibration /src/integrated_detector/representative_pvt_result.json \
  --work /work/schematic-calibration-cases \
  --output /work/schematic-error-calibration.json --jobs 4 --timeout-s 180
python3 /src/integrated_detector/run_composed_error.py --source /src \
  --calibration /src/integrated_detector/representative_pvt_result.json \
  --error-calibration /work/schematic-error-calibration.json \
  --sampler-pex "$sampler" --detector-pex "$detector" --error-pex "$error" \
  --work /work/phase-search-cases --output /work/phase-search.json --jobs 4 --timeout-s 300 \
  --sweep-edge-phase --allow-partial-groups
mkdir -p /work/sampler-retries
for environment in $(python3 /src/integrated_detector/merge_composed_calibration.py \
  --phase-search /work/phase-search.json \
  --base-calibration /src/integrated_detector/representative_pvt_result.json \
  --list-failed); do
  python3 /src/integrated_detector/run_composed_error.py --source /src \
    --calibration /src/integrated_detector/representative_pvt_result.json \
    --error-calibration /work/schematic-error-calibration.json \
    --sampler-pex "$sampler" --detector-pex "$detector" --error-pex "$error" \
    --work "/work/retry-$environment" --output "/work/sampler-retries/$environment.json" \
    --jobs 4 --timeout-s 300 --sweep-edge-phase --sweep-sampler-bias \
    --only-environment "$environment"
done
python3 /src/integrated_detector/merge_composed_calibration.py \
  --phase-search /work/phase-search.json \
  --base-calibration /src/integrated_detector/representative_pvt_result.json \
  --retry-dir /work/sampler-retries \
  --output /work/extracted-calibration.json
python3 /src/integrated_detector/run_composed_error.py --source /src \
  --calibration /work/extracted-calibration.json \
  --error-calibration /work/schematic-error-calibration.json \
  --sampler-pex "$sampler" --detector-pex "$detector" --error-pex "$error" \
  --work /work/replay-cases --output /work/composed-result.json --jobs 4 --timeout-s 300
python3 /src/integrated_detector/summarize_composed_error.py \
  --result /work/composed-result.json \
  --calibration /work/extracted-calibration.json \
  --error-calibration /work/schematic-error-calibration.json \
  --sampler-pex "$sampler" --detector-pex "$detector" --error-pex "$error" \
  --output /work/composed-summary.json
