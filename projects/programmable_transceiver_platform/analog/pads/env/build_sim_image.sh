#!/usr/bin/env bash
# Rebuild the pad simulation image offline from the pinned analog base and the
# recorded ngspice-47 archive plus the two checked-in correction patches.
# Usage: build_sim_image.sh <path-to-ngspice-47.tar.gz>
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pads="$(dirname "$here")"
repo="$(cd "$pads/../../../.." && pwd)"
archive="${1:-$repo/scratch/pad-ngspice47/ngspice-47.tar.gz}"
base="docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3"
tag="svalbard/transceiver-pad-sim:ngspice47-corrected"
echo "894e649651f1838a14095e5a5439e7d3aa63e87ede14d283173fda4fcdef675f  $archive" | sha256sum -c -
docker image inspect "$base" >/dev/null || { echo "pinned base image absent locally" >&2; exit 2; }
ctx="$(mktemp -d "$repo/scratch/pad-sim-context.XXXXXX")"
trap 'rm -rf "$ctx"' EXIT
cp "$here/Dockerfile.sim" "$ctx/Dockerfile"
cp "$archive" "$pads/ngspice-cap-multiplier.patch" "$pads/ngspice-diode-charge.patch" "$ctx/"
DOCKER_BUILDKIT=0 timeout 30m docker build --network none --memory 8g --cpu-quota 400000 -t "$tag" "$ctx"
docker image inspect "$tag" --format 'image_id={{.Id}} arch={{.Architecture}}'
docker run --rm --network none --cpus 1 --memory 1g --entrypoint /bin/cat "$tag" /opt/pad-ngspice47/binary.sha256
