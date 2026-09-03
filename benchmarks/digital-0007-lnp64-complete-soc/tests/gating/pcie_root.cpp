// SPDX-FileCopyrightText: 2026 Deep AI, Inc.
// SPDX-License-Identifier: Apache-2.0
// Root-complex transaction program for the pinned pcievhost model.

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "ltssm.h"
#include "pcieModelClass.h"

namespace {

constexpr unsigned kResetDeasserted = 4;
constexpr uint32_t kBar0 = 0x20000000;
constexpr uint32_t kDmaWords[4] = {
    0x11223344, 0x55667788, 0x99aabbcc, 0xddeeff00,
};

unsigned interrupt_state;
uint8_t completion[4096];
int completion_bytes;

int reset_deasserted(int irq) {
    interrupt_state |= unsigned(irq) & kResetDeasserted;
    return 0;
}

void input_packet(pPkt_t packet, int, void*) {
    if (packet->seq != DLLP_SEQ_ID && packet->ByteCount) {
        auto* payload = GET_TLP_PAYLOAD_PTR(packet->data);
        completion_bytes = packet->ByteCount;
        for (int i = 0; i < completion_bytes; ++i) completion[i] = payload[i];
    }
    DISCARD_PACKET(packet);
}

void word_to_buffer(uint32_t value, PktData_t* buffer) {
    for (unsigned i = 0; i < 4; ++i) buffer[i] = uint8_t(value >> (8 * i));
}

uint32_t completion_word() {
    return uint32_t(completion[0]) | uint32_t(completion[1]) << 8 |
           uint32_t(completion[2]) << 16 | uint32_t(completion[3]) << 24;
}

bool wait_for_completion(pcieModelClass& pcie, unsigned limit = 200000) {
    while (!completion_bytes && limit--) pcie.sendIdle(1);
    return completion_bytes != 0;
}

bool config_read(pcieModelClass& pcie, uint32_t address, unsigned bytes,
                 int& tag, uint32_t& value) {
    completion_bytes = 0;
    pcie.cfgRead(address, bytes, tag++ & 31, 1, SEND);
    if (!wait_for_completion(pcie)) return false;
    value = completion_word();
    return true;
}

void config_write(pcieModelClass& pcie, uint32_t address, uint32_t value,
                  unsigned bytes, int& tag) {
    PktData_t buffer[4]{};
    word_to_buffer(value, buffer);
    pcie.cfgWrite(address, buffer, bytes, tag++ & 31, 1, SEND);
}

[[noreturn]] void stop(pcieModelClass& pcie, const char* message) {
    VPrint("PCIE_ROOT_FAIL: %s\n", message);
    std::fprintf(stderr, "PCIE_ROOT_FAIL: %s\n", message);
    std::fflush(stdout);
    std::fflush(stderr);
    pcie.sendIdle(32);
    VWrite(PVH_FINISH, 0, 0, 0);
    std::abort();
}

}  // namespace

extern "C" void VUserMain0(int node) {
    pcieModelClass pcie(node);
    pcie.initialisePcie(input_packet, nullptr);
    pcie.configurePcie(CONFIG_DISABLE_SCRAMBLING);
    pcie.configurePcie(CONFIG_DISABLE_8B10B);
    pcie.configurePcie(CONFIG_ENABLE_SKIPS, 20000);
    VWrite(LINK_STATE, 0, 0, node);
    VRegIrq(reset_deasserted, node);
    pcie.pcieSeed(0x4c4e5036);
    for (unsigned address = 0x1000; address < 0x3010; address += 4)
        pcie.writeRamWord(address, 0);

    while (!(interrupt_state & kResetDeasserted)) pcie.sendOs(IDL);
    interrupt_state &= ~kResetDeasserted;
    pcie.initLink(1);
    pcie.initFc();

    int tag = 0;
    uint32_t value = 0;
    if (!config_read(pcie, CFG_VENDOR_ID_OFFSET, 4, tag, value) ||
        (value & 0xffff) == 0 || (value & 0xffff) == 0xffff)
        stop(pcie, "invalid vendor/device identity");

    PktData_t probe[4]{};
    word_to_buffer(0xffffffff, probe);
    pcie.cfgWrite(CFG_BAR_HDR_OFFSET, probe, 4, tag++ & 31, 1, SEND);
    if (!config_read(pcie, CFG_BAR_HDR_OFFSET, 4, tag, value) ||
        (value & 0xfffffff0) != 0xffff0000 || (value & 0x7) != 0)
        stop(pcie, "BAR0 is not a 64-KiB non-prefetchable memory BAR");
    config_write(pcie, CFG_BAR_HDR_OFFSET, kBar0, 4, tag);

    uint32_t capability = 0;
    if (!config_read(pcie, CFG_CAPABILITIES_PTR_OFFSET, 1, tag, capability))
        stop(pcie, "configuration capability pointer timed out");
    capability &= 0xff;
    uint32_t msi = 0;
    for (unsigned count = 0; capability && count < 48; ++count) {
        if ((capability & 3) || capability >= 0x1000)
            stop(pcie, "malformed capability list");
        if (!config_read(pcie, capability, 4, tag, value))
            stop(pcie, "capability read timed out");
        if ((value & 0xff) == 5) msi = capability;
        capability = value >> 8 & 0xff;
    }
    if (!msi) stop(pcie, "MSI capability is absent");

    if (!config_read(pcie, msi, 4, tag, value)) stop(pcie, "MSI header timed out");
    const bool msi64 = value & (1u << 23);
    config_write(pcie, msi + 4, 0x00003000, 4, tag);
    unsigned data_offset = 8;
    if (msi64) {
        config_write(pcie, msi + 8, 0, 4, tag);
        data_offset = 12;
    }
    config_write(pcie, msi + data_offset, 0x55aa, 2, tag);
    config_write(pcie, msi, value | (1u << 16), 4, tag);
    config_write(pcie, CFG_COMMAND_OFFSET, 0x0006, 2, tag);

    PktData_t scratch[4]{};
    word_to_buffer(0xc001d00d, scratch);
    pcie.memWrite(kBar0 + 8, scratch, 4, 0, 1, SEND);
    completion_bytes = 0;
    pcie.memRead(kBar0 + 8, 4, tag++ & 31, 1, SEND);
    if (!wait_for_completion(pcie) || completion_word() != 0xc001d00d)
        stop(pcie, "BAR0 scratch read/write failed");

    bool dma_seen = false;
    bool msi_seen = false;
    for (unsigned wait = 0; wait < 500000; ++wait) {
        pcie.sendIdle(1);
        dma_seen = true;
        for (unsigned i = 0; i < 4; ++i)
            dma_seen &= pcie.readRamWord(0x1000 + i * 4, 1) == kDmaWords[i];
        msi_seen = pcie.readRamHWord(0x3000, 1) == 0x55aa;
        if (dma_seen && msi_seen) break;
    }
    if (!dma_seen) stop(pcie, "outbound DMA payload was not received");
    if (!msi_seen) stop(pcie, "MSI write was not received");

    // The program unmaps IOVA zero and attempts a second outbound DMA here.
    // Keep driving the link long enough for the denied operation to settle.
    pcie.sendIdle(20000);
    for (unsigned i = 0; i < 4; ++i)
        if (pcie.readRamWord(0x2000 + i * 4) != 0)
            stop(pcie, "revoked IOVA modified host memory");

    VPrint("PCIE_ROOT_PASS\n");
    std::fflush(stdout);
    if (std::getenv("LNP64_PCIE_ORACLE_SELFTEST")) {
        pcie.sendIdle(1000);
        VWrite(PVH_FINISH, 0, 0, node);
        return;
    }
    while (true) pcie.sendIdle(100);
}
