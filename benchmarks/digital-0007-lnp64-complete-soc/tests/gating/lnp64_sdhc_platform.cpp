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

uint8_t crc7(const std::vector<bool>& bits) {
    uint8_t value = 0;
    for (bool bit : bits) {
        const bool feedback = ((value >> 6) & 1U) ^ bit;
        value = uint8_t((value << 1) & 0x7f);
        if (feedback) value ^= 0x09;
    }
    return value;
}

uint16_t crc16_step(uint16_t value, bool bit) {
    const bool feedback = ((value >> 15) & 1U) ^ bit;
    value = uint16_t(value << 1);
    if (feedback) value ^= 0x1021;
    return value;
}

void push_bits(std::deque<bool>& out, uint64_t value, unsigned count) {
    for (int bit = int(count) - 1; bit >= 0; --bit) out.push_back((value >> bit) & 1U);
}

class SdCard {
  public:
    explicit SdCard(std::vector<uint8_t> sector) : sector_(std::move(sector)) {}

    void observe(Vlnp64_soc& top) {
        const bool clock = top.sd_clk_o;
        if (!last_clock_ && clock) rising(top);
        if (last_clock_ && !clock) falling(top);
        last_clock_ = clock;
    }

    bool passed() const { return selected_ && four_bit_ && read_lba_2048_ && commands_ >= 7; }

  private:
    bool last_clock_ = false;
    bool app_command_ = false;
    bool selected_ = false;
    bool four_bit_ = false;
    bool read_lba_2048_ = false;
    unsigned commands_ = 0;
    unsigned response_delay_ = 0;
    unsigned data_delay_ = 0;
    std::vector<bool> command_;
    std::deque<bool> response_;
    std::deque<uint8_t> data_;
    std::vector<uint8_t> sector_;

    void rising(Vlnp64_soc& top) {
        if (!top.sd_cmd_oe_o) return;
        if (command_.empty() && top.sd_cmd_o) return;
        command_.push_back(top.sd_cmd_o);
        if (command_.size() != 48) return;
        handle_command();
        command_.clear();
    }

    void falling(Vlnp64_soc& top) {
        top.sd_cmd_i = 1;
        top.sd_dat_i = 0xf;
        if (response_delay_) --response_delay_;
        else if (!response_.empty()) {
            top.sd_cmd_i = response_.front();
            response_.pop_front();
        }
        if (data_delay_) --data_delay_;
        else if (!data_.empty()) {
            top.sd_dat_i = data_.front();
            data_.pop_front();
        }
    }

    void response48(unsigned index, uint32_t argument, bool checked = true) {
        std::vector<bool> prefix;
        prefix.push_back(false);
        prefix.push_back(false);
        for (int bit = 5; bit >= 0; --bit) prefix.push_back(index >> bit & 1U);
        for (int bit = 31; bit >= 0; --bit) prefix.push_back(argument >> bit & 1U);
        for (bool bit : prefix) response_.push_back(bit);
        push_bits(response_, checked ? crc7(prefix) : 0x7f, 7);
        response_.push_back(true);
        response_delay_ = 2;
    }

    void response136() {
        response_.push_back(false);
        response_.push_back(false);
        push_bits(response_, 0x3f, 6);
        // Stable synthetic CID/CSD body; CRC covers the preceding 128 bits.
        std::vector<bool> body;
        for (unsigned byte = 0; byte < 15; ++byte)
            for (int bit = 7; bit >= 0; --bit) body.push_back((0x40U + byte) >> bit & 1U);
        for (bool bit : body) response_.push_back(bit);
        std::vector<bool> crc_input(8, false);
        crc_input[2] = crc_input[3] = crc_input[4] = crc_input[5] = crc_input[6] = crc_input[7] = true;
        crc_input.insert(crc_input.end(), body.begin(), body.end());
        push_bits(response_, crc7(crc_input), 7);
        response_.push_back(true);
        response_delay_ = 2;
    }

    void queue_data() {
        std::array<uint16_t, 4> crc{};
        data_.push_back(0x0);
        for (uint8_t byte : sector_) {
            for (uint8_t nibble : {uint8_t(byte >> 4), uint8_t(byte & 0xf)}) {
                data_.push_back(nibble);
                for (unsigned lane = 0; lane < 4; ++lane)
                    crc[lane] = crc16_step(crc[lane], nibble >> lane & 1U);
            }
        }
        for (int bit = 15; bit >= 0; --bit) {
            uint8_t nibble = 0;
            for (unsigned lane = 0; lane < 4; ++lane) nibble |= ((crc[lane] >> bit) & 1U) << lane;
            data_.push_back(nibble);
        }
        data_.push_back(0xf);
        data_delay_ = 58;
    }

    void handle_command() {
        if (command_.front() || !command_[1] || !command_.back())
            throw std::runtime_error("malformed SD command framing");
        if (crc7(std::vector<bool>(command_.begin(), command_.begin() + 40)) !=
            [&] { uint8_t v = 0; for (unsigned i = 40; i < 47; ++i) v = uint8_t(v << 1 | command_[i]); return v; }())
            throw std::runtime_error("SD command CRC7 mismatch");
        unsigned index = 0;
        uint32_t argument = 0;
        for (unsigned i = 2; i < 8; ++i) index = index << 1 | command_[i];
        for (unsigned i = 8; i < 40; ++i) argument = argument << 1 | command_[i];
        ++commands_;
        const bool application = app_command_;
        app_command_ = false;
        if (index == 0) return;
        if (index == 8) return response48(index, 0x000001aa);
        if (index == 55) { app_command_ = true; return response48(index, 0); }
        if (application && index == 41) return response48(index, 0xc0ff8000, false);
        if (index == 2 || index == 9) return response136();
        if (index == 3) return response48(index, 0x12340000);
        if (index == 7) { selected_ = argument == 0x12340000; return response48(index, 0); }
        if (application && index == 6) { four_bit_ = argument == 2; return response48(index, 0); }
        if (index == 13 || index == 16) return response48(index, 0);
        if (index == 17) {
            if (!selected_ || !four_bit_ || argument != 2048)
                throw std::runtime_error("boot read is not four-bit SDHC LBA 2048");
            read_lba_2048_ = true;
            response48(index, 0);
            queue_data();
            return;
        }
        throw std::runtime_error("unsupported SD boot command " + std::to_string(index));
    }
};

class SdramModel {
  public:
    void observe(Vlnp64_soc& top) {
        const bool clock = top.sdram_clk_o;
        if (clock && !last_clock_) rising(top);
        last_clock_ = clock;
    }
    bool transferred() const { return writes_ && reads_; }
  private:
    bool last_clock_ = false;
    std::array<uint16_t, 4> row_{};
    std::array<bool, 4> open_{};
    std::unordered_map<uint32_t, uint32_t> memory_;
    uint32_t pending_ = 0;
    unsigned delay_ = 0, writes_ = 0, reads_ = 0;
    uint32_t address(unsigned bank, unsigned column) const {
        if (!open_[bank]) throw std::runtime_error("SDRAM access without ACTIVE");
        return ((uint32_t(row_[bank]) * 4 + bank) * 1024) + (column & 0x3ff);
    }
    void rising(Vlnp64_soc& top) {
        if (delay_ && --delay_ == 1) top.sdram_dq_i = pending_;
        if (!top.sdram_cke_o || top.sdram_cs_no) return;
        unsigned command = (unsigned(top.sdram_ras_no) << 2) | (unsigned(top.sdram_cas_no) << 1) | top.sdram_we_no;
        unsigned bank = top.sdram_ba_o & 3;
        if (command == 3) { row_[bank] = top.sdram_addr_o & 0x1fff; open_[bank] = true; }
        else if (command == 5) { pending_ = memory_[address(bank, top.sdram_addr_o)]; delay_ = 2; ++reads_; }
        else if (command == 4) {
            uint32_t& value = memory_[address(bank, top.sdram_addr_o)];
            for (unsigned lane = 0; lane < 4; ++lane) if ((top.sdram_dq_oe_o >> lane & 1) && !(top.sdram_dqm_o >> lane & 1)) {
                value = (value & ~(0xffU << lane * 8)) | (((top.sdram_dq_o >> lane * 8) & 0xffU) << lane * 8);
            }
            ++writes_;
        } else if (command == 2) {
            if (top.sdram_addr_o >> 10 & 1) open_.fill(false); else open_[bank] = false;
        }
    }
};

class Harness {
  public:
    explicit Harness(std::vector<uint8_t> sector) : card(std::move(sector)) {
        top.clk_200_i = top.pipe_clk_125_i = top.jtag_tck_i = 0;
        top.rst_ni = top.pcie_perst_ni = top.jtag_trst_ni = 0;
        top.boot_sel_i = 0; top.uart_rx_i = 1; top.sd_cmd_i = 1; top.sd_dat_i = 0xf;
        top.pipe_rxdata_i = top.pipe_rxdatak_i = top.pipe_rxvalid_i = 0;
        top.pipe_phystatus_i = 0; top.pipe_rxelecidle_i = 1; top.pipe_rxstatus_i = 0;
        top.entropy_bit_i = top.entropy_valid_i = 0; top.jtag_tms_i = 1; top.jtag_tdi_i = 0;
        top.sdram_dq_i = 0; top.eval();
    }
    void advance(uint64_t ns) {
        for (uint64_t i = 0; i < ns; ++i) {
            ++time; top.clk_200_i = (time / 5) & 1U; top.pipe_clk_125_i = (time / 8) & 1U;
            top.eval(); card.observe(top); sdram.observe(top); uart(); Verilated::timeInc(1);
        }
    }
    Vlnp64_soc top;
    SdCard card;
    SdramModel sdram;
    std::deque<uint8_t> received;
  private:
    uint64_t time = 0, uart_delay = 0;
    bool uart_last = true, uart_active = false;
    unsigned uart_bit = 0;
    uint8_t uart_byte = 0;
    void uart() {
        bool line = top.uart_tx_o;
        if (!uart_active && uart_last && !line) { uart_active = true; uart_delay = 26041; uart_bit = 0; uart_byte = 0; }
        else if (uart_active && uart_delay && --uart_delay == 0) {
            if (uart_bit < 8) { if (line) uart_byte |= uint8_t{1} << uart_bit; ++uart_bit; uart_delay = 17361; }
            else { if (!line) throw std::runtime_error("UART stop bit malformed"); received.push_back(uart_byte); uart_active = false; }
        }
        uart_last = line;
    }
};

std::vector<uint8_t> read_sector(const char* path) {
    std::ifstream input(path, std::ios::binary);
    std::vector<uint8_t> value{std::istreambuf_iterator<char>(input), {}};
    if (value.size() != 512) throw std::runtime_error("SD fixture sector must be 512 bytes");
    return value;
}

} // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    try {
        if (argc != 2 && argc != 3) throw std::runtime_error("usage: lnp64_sdhc_platform SECTOR [--expect-error]");
        const bool expect_error = argc == 3 && std::string(argv[2]) == "--expect-error";
        std::vector<bool> cmd0(40, false);
        cmd0[1] = true;
        if (crc7(cmd0) != 0x4a) throw std::runtime_error("internal CRC7 oracle failure");
        Harness harness(read_sector(argv[1]));
        harness.advance(200); harness.top.rst_ni = harness.top.pcie_perst_ni = harness.top.jtag_trst_ni = 1;
        for (unsigned block = 0; block < 3000 && !harness.top.boot_done_o && !harness.top.boot_error_o; ++block)
            harness.advance(10'000);
        if (expect_error) {
            if (!harness.top.boot_error_o || harness.top.boot_done_o || harness.top.core_alive_o)
                throw std::runtime_error("corrupt SDHC image was not rejected before execution");
            if (!harness.card.passed()) throw std::runtime_error("corrupt-image SD transfer was incomplete");
            std::cout << "SDHC corrupt-image rejection: PASS\n";
            return 0;
        }
        if (!harness.top.boot_done_o || harness.top.boot_error_o) throw std::runtime_error("valid SDHC image did not boot");
        for (unsigned block = 0; block < 1000 && harness.received.empty(); ++block) harness.advance(10'000);
        if (harness.received.empty() || harness.received.front() != 0x5a) throw std::runtime_error("SDHC-booted program did not execute");
        if (!harness.card.passed()) throw std::runtime_error("SDHC initialization/read coverage incomplete");
        if (!harness.sdram.transferred()) throw std::runtime_error("SDHC boot did not execute through SDRAM");
        std::cout << "SDHC native four-bit boot: PASS\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "SDHC native four-bit boot: FAIL: " << error.what() << "\n";
        return 1;
    }
}
