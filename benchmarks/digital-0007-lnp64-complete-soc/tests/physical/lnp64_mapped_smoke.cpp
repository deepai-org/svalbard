#include <verilated.h>
#include "Vlnp64_soc.h"

#include <cstdint>
#include <iostream>
#include <stdexcept>

namespace {
class Harness {
  public:
    Vlnp64_soc top;

    Harness() {
        top.clk_200_i = 0;
        top.rst_ni = 0;
        top.boot_sel_i = 3;
        top.uart_rx_i = 1;
        top.sd_cmd_i = 1;
        top.sd_dat_i = 0xf;
        top.sdram_dq_i = 0;
        top.pipe_clk_125_i = 0;
        top.pcie_perst_ni = 0;
        top.pipe_rxdata_i = 0;
        top.pipe_rxdatak_i = 0;
        top.pipe_rxvalid_i = 0;
        top.pipe_phystatus_i = 0;
        top.pipe_rxelecidle_i = 1;
        top.pipe_rxstatus_i = 0;
        top.entropy_bit_i = 0;
        top.entropy_valid_i = 0;
        top.jtag_tck_i = 0;
        top.jtag_trst_ni = 0;
        top.jtag_tms_i = 1;
        top.jtag_tdi_i = 0;
        top.eval();
    }

    void advance(unsigned ticks) {
        for (unsigned i = 0; i < ticks; ++i) {
            ++time_;
            top.clk_200_i = ((time_ / 5) & 1U) != 0;
            top.pipe_clk_125_i = ((time_ / 8) & 1U) != 0;
            top.eval();
            Verilated::timeInc(1);
        }
    }

    bool tap_cycle(bool tms, bool tdi) {
        top.jtag_tms_i = tms;
        top.jtag_tdi_i = tdi;
        advance(20);
        top.jtag_tck_i = 1;
        advance(1);
        const bool sample = top.jtag_tdo_o;
        advance(19);
        top.jtag_tck_i = 0;
        top.eval();
        return sample;
    }

    void tap_reset() {
        for (unsigned i = 0; i < 6; ++i) tap_cycle(true, false);
        tap_cycle(false, false);
    }

    void select_ir(unsigned value) {
        tap_cycle(true, false);
        tap_cycle(true, false);
        tap_cycle(false, false);
        tap_cycle(false, false);
        for (unsigned bit = 0; bit < 5; ++bit)
            tap_cycle(bit == 4, value >> bit & 1U);
        tap_cycle(true, false);
        tap_cycle(false, false);
    }

    uint64_t shift_dr(unsigned bits) {
        uint64_t value = 0;
        tap_cycle(true, false);
        tap_cycle(false, false);
        tap_cycle(false, false);
        for (unsigned bit = 0; bit < bits; ++bit)
            if (tap_cycle(bit == bits - 1, false)) value |= uint64_t{1} << bit;
        tap_cycle(true, false);
        tap_cycle(false, false);
        return value;
    }

  private:
    uint64_t time_ = 0;
};
}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    try {
        Harness harness;
        harness.advance(200);
        harness.top.rst_ni = 1;
        harness.top.jtag_trst_ni = 1;
        harness.top.pcie_perst_ni = 1;
        harness.advance(400);
        if (!harness.top.boot_error_o || harness.top.boot_done_o)
            throw std::runtime_error("reserved boot selection was not rejected");

        harness.top.rst_ni = 0;
        harness.top.jtag_trst_ni = 0;
        harness.top.pcie_perst_ni = 0;
        harness.top.boot_sel_i = 2;
        harness.advance(200);
        harness.top.rst_ni = 1;
        harness.top.jtag_trst_ni = 1;
        harness.top.pcie_perst_ni = 1;
        harness.advance(200);
        harness.tap_reset();
        harness.select_ir(1);
        if (harness.shift_dr(32) != 0x0e64964dU)
            throw std::runtime_error("JTAG IDCODE mismatch");
        harness.select_ir(9);
        const uint64_t status = harness.shift_dr(32);
        if (!(status & 1U) || (status & 8U) || (status & 0xf0U))
            throw std::runtime_error("JTAG reset target status mismatch");
        std::cout << "mapped GF180 smoke: PASS\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "mapped GF180 smoke: FAIL: " << error.what() << "\n";
        return 1;
    }
}
