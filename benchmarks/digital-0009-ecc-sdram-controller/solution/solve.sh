#!/bin/sh
set -eu
mkdir -p /app/output/rtl
cp "$(dirname "$0")/golden_output/rtl/ecc_sdram_controller.sv" /app/output/rtl/
