#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
exec "$repo_root/scripts/run_analog_flow.sh" --label transceiver-gpio-transient \
 --source-rel projects/programmable_transceiver_platform --timeout 5m --cpus 2 --memory 4g \
 --command /src/verification/container_gpio_transient.sh \
 --require-result-json gpio-transient.json --copy gpio-transient.json:transceiver-gpio-transient.json
