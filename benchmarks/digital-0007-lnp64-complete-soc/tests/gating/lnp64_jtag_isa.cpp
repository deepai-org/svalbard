#include <verilated.h>
#include "Vlnp64_soc.h"

#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr uint8_t IR_IDCODE = 1;
constexpr uint8_t IR_RESUME = 3;
constexpr uint8_t IR_REGADDR = 5;
constexpr uint8_t IR_REGDATA = 6;
constexpr uint8_t IR_MEMADDR = 7;
constexpr uint8_t IR_MEMDATA = 8;
constexpr uint8_t IR_STATUS = 9;
constexpr uint32_t EXPECTED_IDCODE = 0x0e64964d;
constexpr char ENTROPY_HEX[] =
    "6971c1321a8fe6d42d566c4c73f8b09c741491cb152903b18b77799fc7f6fc8d"
    "08863e5d5c39c836512ccf1259f290b7";

struct Case {
    std::string name;
    std::string stem;
    uint64_t attempted = 0;
    std::string transport;
    uint64_t exit_value = 0;
    uint64_t r3 = 0;
    uint64_t r4 = 0;
    uint64_t r5 = 0;
    uint64_t r6 = 0;
    uint64_t mem0 = 0;
    uint64_t data0 = 0;
    uint64_t error_number = 0;
};

class Harness {
  public:
    Vlnp64_soc top;

    Harness() {
        top.clk_200_i = 0;
        top.rst_ni = 0;
        top.boot_sel_i = 2;
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
        top.eval();
    }

    void advance(unsigned half_ns) {
        for (unsigned i = 0; i < half_ns; ++i) {
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
        top.jtag_tck_i = 0;
        advance(40);
        top.jtag_tck_i = 1;
        advance(1);
        const bool tdo = top.jtag_tdo_o;
        advance(39);
        return tdo;
    }

    void tap_reset() {
        for (int i = 0; i < 6; ++i) tap_cycle(true, false);
        tap_cycle(false, false);
    }

    std::vector<bool> shift(bool ir, const std::vector<bool>& tx) {
        tap_cycle(true, false);               // Select-DR
        if (ir) tap_cycle(true, false);       // Select-IR
        tap_cycle(false, false);              // Capture
        tap_cycle(false, false);              // Shift
        std::vector<bool> rx(tx.size());
        for (size_t i = 0; i < tx.size(); ++i)
            rx[i] = tap_cycle(i + 1 == tx.size(), tx[i]);
        tap_cycle(true, false);               // Update
        tap_cycle(false, false);              // Idle
        return rx;
    }

    void select_ir(uint8_t value) { shift(true, bits(value, 5)); }

    uint64_t shift_dr64(uint64_t value, unsigned width) {
        auto rx = shift(false, bits(value, width));
        uint64_t result = 0;
        for (unsigned i = 0; i < width && i < 64; ++i)
            if (rx[i]) result |= uint64_t{1} << i;
        return result;
    }

    uint64_t read_reg(uint16_t address) {
        select_ir(IR_REGADDR);
        shift_dr64(address, 17);
        select_ir(IR_REGDATA);
        return shift_dr64(0, 512);
    }

    void write_reg(uint16_t address, uint64_t value) {
        select_ir(IR_REGADDR);
        shift_dr64((uint64_t{1} << 16) | address, 17);
        select_ir(IR_REGDATA);
        shift_dr64(value, 512);
    }

    uint64_t read_mem(uint64_t address) {
        select_ir(IR_MEMADDR);
        shift_dr64(address, 65);
        select_ir(IR_MEMDATA);
        return shift_dr64(0, 64);
    }

    void write_mem(uint64_t address, uint64_t value) {
        select_ir(IR_MEMADDR);
        auto address_bits = bits(address, 65);
        address_bits[64] = true;
        shift(false, address_bits);
        select_ir(IR_MEMDATA);
        shift_dr64(value, 64);
    }

    uint32_t status() {
        select_ir(IR_STATUS);
        return static_cast<uint32_t>(shift_dr64(0, 32));
    }

    void reset_case() {
        top.rst_ni = 0;
        top.jtag_trst_ni = 0;
        top.pcie_perst_ni = 0;
        advance(200);
        top.rst_ni = 1;
        top.jtag_trst_ni = 1;
        top.pcie_perst_ni = 1;
        tap_reset();
        select_ir(IR_IDCODE);
        if (shift_dr64(0, 32) != EXPECTED_IDCODE)
            throw std::runtime_error("JTAG IDCODE mismatch");
        for (unsigned poll = 0; poll < 128; ++poll) {
            if (status() & 1U) {
                seed_entropy();
                return;
            }
        }
        throw std::runtime_error("JTAG boot target did not halt after memory initialization");
    }

    void resume_and_wait(const Case& row) {
        select_ir(IR_RESUME);
        shift_dr64(1, 1);
        const uint64_t limit = std::max<uint64_t>(128, row.attempted * 8 + 32);
        for (uint64_t poll = 0; poll < limit; ++poll) {
            if (status() & 1U) return;
        }
        throw std::runtime_error("execution timeout");
    }

  private:
    uint64_t time_ = 0;

    static std::vector<bool> bits(uint64_t value, unsigned width) {
        std::vector<bool> result(width);
        for (unsigned i = 0; i < width && i < 64; ++i)
            result[i] = ((value >> i) & 1U) != 0;
        return result;
    }

    void seed_entropy() {
        for (char hex : std::string(ENTROPY_HEX)) {
            unsigned nibble = hex <= '9' ? unsigned(hex - '0') : unsigned(hex - 'a' + 10);
            for (int bit = 3; bit >= 0; --bit) {
                unsigned waited = 0;
                while (!top.entropy_ready_o && waited++ < 4096) advance(10);
                if (!top.entropy_ready_o)
                    throw std::runtime_error("entropy conditioner did not become ready");
                top.entropy_bit_i = nibble >> bit & 1U;
                top.entropy_valid_i = 1;
                advance(10);
            }
        }
        top.entropy_valid_i = 0;
        top.entropy_bit_i = 0;
        advance(10);
    }
};

uint64_t parse_u64(const std::string& text) {
    if (text.empty()) return 0;
    size_t used = 0;
    uint64_t value = std::stoull(text, &used, 0);
    if (used != text.size()) throw std::runtime_error("invalid integer: " + text);
    return value;
}

std::vector<std::string> split_tabs(const std::string& line) {
    std::vector<std::string> fields;
    std::stringstream stream(line);
    std::string field;
    while (std::getline(stream, field, '\t')) fields.push_back(field);
    while (fields.size() < 12) fields.emplace_back();
    return fields;
}

std::vector<Case> load_cases(const std::string& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open case manifest");
    std::vector<Case> result;
    for (std::string line; std::getline(input, line);) {
        if (line.empty() || line[0] == '#') continue;
        auto f = split_tabs(line);
        if (f.size() != 12) throw std::runtime_error("malformed case manifest row");
        result.push_back({f[0], f[1], parse_u64(f[2]), f[3], parse_u64(f[4]),
                          parse_u64(f[5]), parse_u64(f[6]), parse_u64(f[7]),
                          parse_u64(f[8]), parse_u64(f[9]), parse_u64(f[10]),
                          parse_u64(f[11])});
    }
    return result;
}

std::vector<uint64_t> load_hex(const std::string& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open image: " + path);
    std::vector<uint64_t> result;
    for (std::string line; std::getline(input, line);) {
        if (line.empty()) continue;
        result.push_back(std::stoull(line, nullptr, 16));
    }
    return result;
}

void require_equal(const Case& row, const char* field, uint64_t got, uint64_t expected) {
    if (got == expected) return;
    std::ostringstream message;
    message << row.name << ": " << field << " got 0x" << std::hex << got
            << ", expected 0x" << expected;
    throw std::runtime_error(message.str());
}

void run_case(Harness& harness, const Case& row, const std::string& image_dir) {
    harness.reset_case();
    const auto text = load_hex(image_dir + "/" + row.stem + ".hex");
    const auto data = load_hex(image_dir + "/" + row.stem + ".data.hex");
    for (size_t i = 0; i < text.size(); ++i)
        harness.write_mem(0x1000 + i * 8, text[i]);
    for (size_t i = 0; i < data.size(); ++i)
        harness.write_mem(0x10000 + i * 8, data[i]);
    harness.write_reg(0x40, 0x1000);
    harness.resume_and_wait(row);

    const uint64_t stop_cause = harness.read_reg(0x42);
    if (row.transport == "architectural-fault") {
        require_equal(row, "stop cause", stop_cause, 3);
        return;
    }
    require_equal(row, "stop cause", stop_cause, 2);
    require_equal(row, "exit", harness.read_reg(0x43), row.exit_value);
    require_equal(row, "r3", harness.read_reg(3), row.r3);
    require_equal(row, "r4", harness.read_reg(4), row.r4);
    require_equal(row, "r5", harness.read_reg(5), row.r5);
    require_equal(row, "r6", harness.read_reg(6), row.r6);
    require_equal(row, "errno", harness.read_reg(0x45), row.error_number);
    require_equal(row, "mem0", harness.read_mem(0), row.mem0);
    require_equal(row, "data0", harness.read_mem(0x10000), row.data0);
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    if (argc != 3) {
        std::cerr << "usage: lnp64_jtag_isa CASES.tsv IMAGE_DIR\n";
        return 2;
    }
    try {
        const auto cases = load_cases(argv[1]);
        if (cases.empty()) throw std::runtime_error("case manifest is empty");
        Harness harness;
        size_t passed = 0;
        for (const auto& row : cases) {
            run_case(harness, row, argv[2]);
            ++passed;
            if (passed % 50 == 0) std::cout << "ISA progress " << passed << "/" << cases.size() << "\n";
        }
        std::cout << "LNP64 JTAG ISA PASS (" << passed << " cases)\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "LNP64 JTAG ISA FAIL: " << error.what() << "\n";
        return 1;
    }
}
