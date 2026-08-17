#!/usr/bin/env python3
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: transition_fault.py NETLIST OUTPUT_JSON")

netlist, output = map(Path, sys.argv[1:])
text = netlist.read_text()
sites = sorted(
    {
        net
        for net in re.findall(r"\.(?:Q|Z|ZN)\(([A-Za-z_][A-Za-z0-9_$]*)\)", text)
        if net != "scan_out_0"
    }
)
if not 8 <= len(sites) <= 32:
    raise SystemExit(f"unexpected transition site count: {len(sites)}")

read_cases = "\n".join(
    f"            {index}: site_value = dut.{net};"
    for index, net in enumerate(sites)
)
force_zero_cases = "\n".join(
    f"                {index}: force dut.{net} = 1'b0;"
    for index, net in enumerate(sites)
)
force_one_cases = "\n".join(
    f"                {index}: force dut.{net} = 1'b1;"
    for index, net in enumerate(sites)
)
release_cases = "\n".join(
    f"            {index}: release dut.{net};" for index, net in enumerate(sites)
)
testbench = f"""`timescale 1ns/1ps
module transition_fault_tb;
    reg clk = 0;
    reg rst = 1;
    reg scan_enable_0 = 0;
    reg scan_in_0 = 0;
    wire scan_out_0;
    wire [3:0] count;
    integer fault_index;
    integer direction;
    integer state;
    integer expected;
    reg old_value;
    reg new_value;

    counter dut (.clk(clk), .rst(rst), .count(count),
        .scan_enable_0(scan_enable_0), .scan_in_0(scan_in_0),
        .scan_out_0(scan_out_0));
    always #5 clk = ~clk;

    function site_value;
        input integer index;
        begin
            case (index)
{read_cases}
                default: site_value = 1'bx;
            endcase
        end
    endfunction
    task apply_fault;
        if (direction == 0) begin
            case (fault_index)
{force_zero_cases}
                default: $fatal(1, "bad fault index");
            endcase
        end else begin
            case (fault_index)
{force_one_cases}
                default: $fatal(1, "bad fault index");
            endcase
        end
    endtask
    task release_fault;
        case (fault_index)
{release_cases}
        endcase
    endtask
    task reset_counter;
        begin
            rst = 1;
            repeat (2) @(posedge clk);
            #1;
            rst = 0;
        end
    endtask

    initial begin
        if (!$value$plusargs("fault=%d", fault_index)) $fatal(1, "fault missing");
        if (!$value$plusargs("direction=%d", direction)) $fatal(1, "direction missing");
        if (direction != 0 && direction != 1) $fatal(1, "bad direction");

        reset_counter();
        repeat (3) @(posedge clk);
        #1;
        old_value = site_value(fault_index);
        rst = 1;
        #1;
        new_value = site_value(fault_index);
        if (old_value === direction[0] && new_value === ~direction[0]) begin
            apply_fault();
            @(posedge clk);
            #1;
            if (count !== 0) begin
                release_fault();
                $display("DETECT 16");
                $finish;
            end
            release_fault();
        end

        rst = 1;
        repeat (2) @(posedge clk);
        #1;
        old_value = site_value(fault_index);
        rst = 0;
        #1;
        new_value = site_value(fault_index);
        if (old_value === direction[0] && new_value === ~direction[0]) begin
            apply_fault();
            @(posedge clk);
            #1;
            if (count !== 1) begin
                release_fault();
                $display("DETECT 17");
                $finish;
            end
            release_fault();
        end

        for (state = 0; state < 16; state = state + 1) begin
            reset_counter();
            repeat (state) @(posedge clk);
            #1;
            old_value = site_value(fault_index);
            @(posedge clk);
            #1;
            new_value = site_value(fault_index);
            if (old_value === direction[0] && new_value === ~direction[0]) begin
                apply_fault();
                expected = (state + 2) & 15;
                @(posedge clk);
                #1;
                if (count !== expected[3:0]) begin
                    release_fault();
                    $display("DETECT %0d", state);
                    $finish;
                end
                release_fault();
            end
        end
        $fatal(1, "undetected");
    end
endmodule
"""

work = Path("/work")
tb = work / "transition_fault_tb.v"
sim = work / "transition_fault_sim"
tb.write_text(testbench)
pdk = Path("/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog")
subprocess.run(
    [
        "iverilog",
        "-g2012",
        "-DFUNCTIONAL",
        "-s",
        "transition_fault_tb",
        "-o",
        str(sim),
        str(pdk / "primitives.v"),
        str(pdk / "gf180mcu_fd_sc_mcu7t5v0.v"),
        str(netlist),
        str(tb),
    ],
    check=True,
    timeout=60,
)

patterns = {}
for index, site in enumerate(sites):
    for direction, name in ((0, "str"), (1, "stf")):
        run = subprocess.run(
            ["vvp", str(sim), f"+fault={index}", f"+direction={direction}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        match = re.search(r"DETECT (\d+)", run.stdout)
        if run.returncode != 0 or match is None:
            raise SystemExit(f"undetected transition fault: {site}/{name}")
        patterns[f"{site}/{name}"] = int(match.group(1))

result = {
    "schema_version": 1,
    "netlist_sha256": hashlib.sha256(netlist.read_bytes()).hexdigest(),
    "pattern_ids": {"reset_assert": 16, "reset_deassert": 17},
    "sites": sites,
    "faults": len(patterns),
    "detected": len(patterns),
    "patterns": patterns,
}
output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"transition-fault: {len(patterns)}/{len(patterns)} PASS")
