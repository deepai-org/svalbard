#!/bin/sh
set -eu
base=$(dirname "$0")/golden_output
mkdir -p /app/output/analog /app/output/layout /app/output/integration
cp "$base/analog/dco4.spice" /app/output/analog/
cp "$base/layout/dco4.gds" /app/output/layout/
cp "$base/integration/dco4.json" /app/output/integration/
