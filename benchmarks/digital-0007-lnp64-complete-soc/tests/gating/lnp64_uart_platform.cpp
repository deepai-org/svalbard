#include <verilated.h>
#include "Vlnp64_soc.h"

#include <array>
#include <cstdint>
#include <deque>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

constexpr uint64_t UART_BIT_HALF_NS = 17361;

class SdramModel {
  public:
    void observe(Vlnp64_soc& top) {
        const bool clock = top.sdram_clk_o;
        if (clock && !last_clock_) rising(top);
        last_clock_ = clock;
    }

    bool initialized() const { return active_count_ && precharge_count_ && refresh_count_ >= 2 && mode_count_; }
    bool transferred() const { return writes_ && reads_; }
    bool refresh_healthy() const { return max_refresh_gap_ <= 781; }

  private:
    bool last_clock_ = false;
    std::array<uint16_t, 4> row_{};
    std::array<bool, 4> row_open_{};
    std::unordered_map<uint32_t, uint32_t> memory_;
    uint32_t pending_data_ = 0;
    unsigned pending_delay_ = 0;
    unsigned refresh_gap_ = 0;
    unsigned max_refresh_gap_ = 0;
    unsigned active_count_ = 0;
    unsigned precharge_count_ = 0;
    unsigned refresh_count_ = 0;
    unsigned mode_count_ = 0;
    unsigned writes_ = 0;
    unsigned reads_ = 0;

    uint32_t word_address(unsigned bank, unsigned column) const {
        if (!row_open_[bank]) throw std::runtime_error("SDRAM access without ACTIVE row");
        return ((uint32_t(row_[bank]) * 4 + bank) * 1024) + (column & 0x3ff);
    }

    void rising(Vlnp64_soc& top) {
        if (pending_delay_) {
            --pending_delay_;
            if (pending_delay_ == 1) top.sdram_dq_i = pending_data_;
        }
        if (!top.sdram_cke_o) return;
        ++refresh_gap_;
        if (refresh_gap_ > max_refresh_gap_) max_refresh_gap_ = refresh_gap_;
        if (top.sdram_cs_no) return;
        const unsigned command = (unsigned(top.sdram_ras_no) << 2)
                               | (unsigned(top.sdram_cas_no) << 1)
                               | unsigned(top.sdram_we_no);
        const unsigned bank = top.sdram_ba_o & 3;
        switch (command) {
          case 3:  // ACTIVE: 0,1,1
            row_[bank] = top.sdram_addr_o & 0x1fff;
            row_open_[bank] = true;
            ++active_count_;
            break;
          case 5: {  // READ: 1,0,1
            const uint32_t address = word_address(bank, top.sdram_addr_o);
            pending_data_ = memory_[address];
            pending_delay_ = 2;
            ++reads_;
            break;
          }
          case 4: {  // WRITE: 1,0,0
            const uint32_t address = word_address(bank, top.sdram_addr_o);
            uint32_t value = memory_[address];
            for (unsigned lane = 0; lane < 4; ++lane) {
                if ((top.sdram_dq_oe_o >> lane & 1) && !(top.sdram_dqm_o >> lane & 1)) {
                    value &= ~(uint32_t(0xff) << (lane * 8));
                    value |= ((top.sdram_dq_o >> (lane * 8)) & 0xff) << (lane * 8);
                }
            }
            memory_[address] = value;
            ++writes_;
            break;
          }
          case 2:  // PRECHARGE: 0,1,0
            if (top.sdram_addr_o >> 10 & 1) row_open_.fill(false);
            else row_open_[bank] = false;
            ++precharge_count_;
            break;
          case 1:  // AUTO REFRESH: 0,0,1
            ++refresh_count_;
            refresh_gap_ = 0;
            break;
          case 0:  // LOAD MODE REGISTER: 0,0,0
            ++mode_count_;
            break;
          default: // NOP or burst terminate
            break;
        }
    }
};

class Harness {
  public:
    Vlnp64_soc top;
    SdramModel sdram;

    Harness() {
        top.clk_200_i = 0;
        top.rst_ni = 0;
        top.boot_sel_i = 1;
        top.uart_rx_i = 1;
        top.sd_cmd_i = 1;
        top.sd_dat_i = 0xf;
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
        top.sdram_dq_i = 0;
        top.eval();
    }

    void advance(uint64_t half_ns) {
        for (uint64_t i = 0; i < half_ns; ++i) {
            ++time_;
            top.clk_200_i = ((time_ / 5) & 1U) != 0;
            top.pipe_clk_125_i = ((time_ / 8) & 1U) != 0;
            top.eval();
            sdram.observe(top);
            monitor_uart();
            Verilated::timeInc(1);
        }
    }

    void reset() {
        advance(200);
        top.rst_ni = 1;
        top.jtag_trst_ni = 1;
        top.pcie_perst_ni = 1;
        advance(200);
    }

    void send_uart_byte(uint8_t value) {
        top.uart_rx_i = 0;
        advance(UART_BIT_HALF_NS);
        for (unsigned bit = 0; bit < 8; ++bit) {
            top.uart_rx_i = value >> bit & 1;
            advance(UART_BIT_HALF_NS);
        }
        top.uart_rx_i = 1;
        advance(UART_BIT_HALF_NS);
    }

    uint8_t receive_uart_byte() {
        for (uint64_t wait = 0; wait < 2'000'000 && received_.empty(); ++wait)
            advance(10);
        if (received_.empty()) throw std::runtime_error("UART transmit timeout");
        const uint8_t value = received_.front();
        received_.pop_front();
        return value;
    }

  private:
    uint64_t time_ = 0;
    bool uart_last_ = true;
    bool uart_capture_ = false;
    uint64_t uart_sample_delay_ = 0;
    unsigned uart_sample_bit_ = 0;
    uint8_t uart_sample_byte_ = 0;
    std::deque<uint8_t> received_;

    void monitor_uart() {
        const bool line = top.uart_tx_o;
        if (!top.rst_ni) {
            uart_last_ = line;
            uart_capture_ = false;
            received_.clear();
            return;
        }
        if (!uart_capture_ && uart_last_ && !line) {
            uart_capture_ = true;
            uart_sample_delay_ = UART_BIT_HALF_NS + UART_BIT_HALF_NS / 2;
            uart_sample_bit_ = 0;
            uart_sample_byte_ = 0;
        } else if (uart_capture_ && uart_sample_delay_) {
            --uart_sample_delay_;
            if (uart_sample_delay_ == 0) {
                if (uart_sample_bit_ < 8) {
                    if (line) uart_sample_byte_ |= uint8_t{1} << uart_sample_bit_;
                    ++uart_sample_bit_;
                    uart_sample_delay_ = UART_BIT_HALF_NS;
                } else {
                    if (!line) throw std::runtime_error("UART stop bit is malformed");
                    received_.push_back(uart_sample_byte_);
                    uart_capture_ = false;
                }
            }
        }
        uart_last_ = line;
    }
};

std::vector<uint8_t> read_bytes(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot open UART boot frame");
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    if (argc != 2) {
        std::cerr << "usage: lnp64_uart_platform UART_FRAME\n";
        return 2;
    }
    try {
        Harness harness;
        harness.reset();
        for (uint8_t byte : read_bytes(argv[1])) harness.send_uart_byte(byte);
        for (unsigned cycle = 0; cycle < 20000 && !harness.top.boot_done_o; ++cycle)
            harness.advance(10);
        if (!harness.top.boot_done_o || harness.top.boot_error_o)
            throw std::runtime_error("valid UART image did not boot");
        for (unsigned cycle = 0; cycle < 20000 && harness.top.core_alive_o != 0xf; ++cycle)
            harness.advance(10);
        if (harness.top.core_alive_o != 0xf)
            throw std::runtime_error("four cores did not join after boot");
        const unsigned uart_byte = harness.receive_uart_byte();
        if (uart_byte != 0x5a)
            throw std::runtime_error("booted UART program returned byte " + std::to_string(uart_byte));
        if (!harness.sdram.initialized())
            throw std::runtime_error("SDRAM initialization sequence is incomplete");
        if (!harness.sdram.transferred())
            throw std::runtime_error("boot did not read and write SDRAM");
        if (!harness.sdram.refresh_healthy())
            throw std::runtime_error("SDRAM refresh deadline was exceeded");
        std::cout << "UART boot and SDRAM integration: PASS\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "UART boot and SDRAM integration: FAIL: " << error.what() << "\n";
        return 1;
    }
}
