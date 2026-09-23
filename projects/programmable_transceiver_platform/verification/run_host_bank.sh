#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
case "${1:-}" in
 '') stem=host-bank; bank_command=/src/screen_host_bank.py ;;
 --isolate) stem=host-bank-isolation; bank_command=/src/container_host_bank_isolation.sh ;;
 *) printf 'usage: %s [--isolate]\n' "$0" >&2; exit 2 ;;
esac
exec "$repo_root/scripts/run_analog_flow.sh" --label "transceiver-$stem" \
 --source-rel projects/programmable_transceiver_platform/verification \
 --timeout 5m --cpus 2 --memory 4g --command "$bank_command" \
 --copy "$stem.json:transceiver-$stem.json" \
 --copy "$stem-waveforms.tar.gz:transceiver-$stem-waveforms.tar.gz"
