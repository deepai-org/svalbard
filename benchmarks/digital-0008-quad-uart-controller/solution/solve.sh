#!/bin/sh
set -eu
mkdir -p /app/output/rtl
cp "$(dirname "$0")/golden_output/rtl/quad_uart_controller.sv" /app/output/rtl/
