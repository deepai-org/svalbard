#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
for environment in ff_cold ff_hot ss_cold; do
  test -s "$(dirname "${BASH_SOURCE[0]}")/replay_logs/$environment.log" || {
    printf 'missing replay log: %s\n' "$environment" >&2
    exit 2
  }
done
exec "$repo_root/scripts/run_analog_flow.sh" \
  --label pcie-event-lane-routed-parent-exact-pex-replay \
  --source-rel ip/blocks/analog/wireline_serdes \
  --command /src/event_lane_routed_parent/container_replay_exact_pex_remaining.sh \
  --timeout 5m --cpus 2 --memory 4g \
  --copy event_lane_routed_parent_exact_pex_remaining.json:pcie-event-lane-routed-parent-exact-pex-remaining-last.json
