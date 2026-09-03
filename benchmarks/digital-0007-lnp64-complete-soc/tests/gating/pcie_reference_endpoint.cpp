// SPDX-FileCopyrightText: 2026 Deep AI, Inc.
// SPDX-License-Identifier: Apache-2.0
// Known-good protocol peer used only to validate the PCIe root oracle.

#include <cstdint>
#include <cstdlib>

#include "ltssm.h"
#include "pcieModelClass.h"

namespace {
constexpr unsigned kResetDeasserted = 4;
unsigned interrupt_state;

int reset_deasserted(int irq) {
    interrupt_state |= unsigned(irq) & kResetDeasserted;
    return 0;
}

void discard(pPkt_t packet, int, void*) { DISCARD_PACKET(packet); }

void configure_endpoint(pcieModelClass& pcie) {
    // Type-0 header: one 64-KiB 32-bit memory BAR and capabilities list.
    pcie.writeConfigSpace(0x00, 0x60454c4e); // device 6045, vendor "LN"
    pcie.writeConfigSpace(0x04, 0x00100000); // capabilities-list status
    pcie.writeConfigSpaceMask(0x04, 0xfff8fff8);
    pcie.writeConfigSpace(0x08, 0x05000001); // memory controller, revision 1
    pcie.writeConfigSpace(0x0c, 0x00000000); // type-0 header
    pcie.writeConfigSpace(0x10, 0x00000000);
    pcie.writeConfigSpaceMask(0x10, 0x0000ffff);
    for (unsigned offset = 0x14; offset <= 0x24; offset += 4) {
        pcie.writeConfigSpace(offset, 0);
        pcie.writeConfigSpaceMask(offset, 0xffffffff);
    }
    pcie.writeConfigSpace(0x34, 0x00000040);

    // A single-vector, 64-bit MSI capability.
    pcie.writeConfigSpace(0x40, 0x00800005);
    pcie.writeConfigSpaceMask(0x40, 0xfffeffff);
    pcie.writeConfigSpace(0x44, 0);
    pcie.writeConfigSpaceMask(0x44, 0x00000003);
    pcie.writeConfigSpace(0x48, 0);
    pcie.writeConfigSpaceMask(0x48, 0x00000000);
    pcie.writeConfigSpace(0x4c, 0);
    pcie.writeConfigSpaceMask(0x4c, 0xffff0000);
}
}  // namespace

extern "C" void VUserMain1(int node) {
    pcieModelClass pcie(node);
    pcie.initialisePcie(discard, nullptr);
    pcie.configurePcie(CONFIG_DISABLE_SCRAMBLING);
    pcie.configurePcie(CONFIG_DISABLE_8B10B);
    VWrite(LINK_STATE, 0, 0, node);
    VRegIrq(reset_deasserted, node);
    pcie.pcieSeed(0x6045);
    configure_endpoint(pcie);

    while (!(interrupt_state & kResetDeasserted)) pcie.sendOs(IDL);
    pcie.initLink(1);
    pcie.initFc();

    // Let enumeration transactions drain, then act like the candidate's two
    // successful outbound writes. All request processing stays on this model
    // thread; no racy inspection of its configuration backing store is used.
    pcie.sendIdle(20000);

    PktData_t payload[16] = {
        0x44, 0x33, 0x22, 0x11, 0x88, 0x77, 0x66, 0x55,
        0xcc, 0xbb, 0xaa, 0x99, 0x00, 0xff, 0xee, 0xdd,
    };
    pcie.memWrite(0x1000, payload, 16, 0, 1, SEND);
    PktData_t msi[2] = {0xaa, 0x55};
    pcie.memWrite(0x3000, msi, 2, 0, 1, SEND);
    VPrint("PCIE_REFERENCE_ENDPOINT_PASS\n");
    while (true) pcie.sendIdle(100);
}
