#!/bin/bash
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
serdes=$(cd "$here/.." && pwd)
repo=$(cd "$here/../../../../.." && pwd)
work=$(mktemp -d "$repo/scratch/pcie-event-start-end-sr-screen.XXXXXXXX")
trap 'rm -rf "$work"' EXIT

source_hash=$(sha256sum "$here/compile_event_capture_state_free_sr_source.py" | cut -d' ' -f1)
timeout --kill-after=30s 20m docker run --rm --platform linux/arm64 \
  --cpus=8 --memory=12g --memory-swap=12g --pids-limit=256 --network=none \
  --read-only --cap-drop=ALL --security-opt=no-new-privileges --user 1000:1000 \
  --env HOME=/tmp --env PDK=gf180mcuD --env ANALOG_SOURCE_SHA256="$source_hash" \
  --env PDKPATH=/foss/pdks/gf180mcuD --workdir /work \
  --mount type=bind,src="$serdes",dst=/src,readonly \
  --mount type=bind,src="$work",dst=/work \
  --tmpfs /tmp:size=256m,mode=1777 \
  --tmpfs /headless/.data-default:size=16m,mode=0700,uid=1000,gid=1000 \
  --entrypoint /bin/bash \
  docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3 \
  -lc /src/clock_pulse_hclk_window_probe/container_event_start_end_sr_screen.sh || status=$?
status=${status:-0}
cp "$work/start-end-sr-screen.json" "$repo/scratch/pcie-event-start-end-sr-screen-last.json"
echo "pcie-event-start-end-sr-screen: output $repo/scratch/pcie-event-start-end-sr-screen-last.json"
exit "$status"
