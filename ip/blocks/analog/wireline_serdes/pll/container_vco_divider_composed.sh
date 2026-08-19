#!/usr/bin/env bash
set -euo pipefail
cd /work

# These are byte-identical PEX decks emitted by the physical closure flows and
# bound by their committed evidence.  Keeping them makes the composition
# reproducible despite the extractor's nondeterministic timestamp header.
python3 /src/pll/run_vco_divider_composed.py --source /src/pll \
  --vco-pex /src/pll/pex/vco_bank_top.pex.spice \
  --divider-pex /src/pll/pex/divider.pex.spice \
  --vco-baseline /src/pll/vco_bank_top_pvt_result.json \
  --divider-physical /src/pll/divider_physical_result.json \
  ${VCO_DIVIDER_EXTRA_ARGS:-} \
  --work /work/vco-divider-composed-sim \
  --output /work/vco-divider-composed-result.json
