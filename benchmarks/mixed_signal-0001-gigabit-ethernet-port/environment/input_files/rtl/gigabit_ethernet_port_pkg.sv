`ifndef GIGABIT_ETHERNET_PORT_PKG_SV
`define GIGABIT_ETHERNET_PORT_PKG_SV
`timescale 1ns/1ps

package gigabit_ethernet_port_pkg;
  parameter int unsigned DATA_W = 8;
  parameter int unsigned CTRL_W = 16;
  parameter int unsigned COUNTER_W = 32;
  parameter int unsigned CTRL_ENABLE_BIT = 0;
  parameter int unsigned CTRL_LOOPBACK_LSB = 1;
  parameter int unsigned CTRL_SWING_LSB = 3;
  parameter int unsigned CTRL_THRESHOLD_LSB = 6;
  parameter int unsigned CTRL_BIAS_LSB = 9;
  parameter int unsigned CTRL_CDR_LSB = 13;
  parameter int unsigned STATUS_ENABLED_BIT = 0;
  parameter int unsigned STATUS_PHY_LOCK_BIT = 1;
  parameter int unsigned STATUS_LINK_UP_BIT = 2;
  parameter int unsigned STATUS_CONFIG_DONE_BIT = 3;
  parameter int unsigned STATUS_FAULT_BIT = 4;
  typedef enum logic [1:0] {
    LOOPBACK_NONE    = 2'd0,
    LOOPBACK_DIGITAL = 2'd1,
    LOOPBACK_PCS     = 2'd2,
    LOOPBACK_ANALOG  = 2'd3
  } loopback_mode_t;
endpackage

`endif
