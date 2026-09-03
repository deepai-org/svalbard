"""Independent, architecture-neutral Ethernet frame oracle.

This code defines externally observable benchmark arithmetic.  It is not RTL
and makes no microarchitecture recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_PAYLOAD_BYTES = 46
MAX_PAYLOAD_BYTES = 1500
ETH_HEADER_BYTES = 14
FCS_BYTES = 4
CRC32_REFLECTED_POLY = 0xEDB88320


def ethernet_crc32(data: bytes) -> int:
    """Return reflected Ethernet CRC-32 with initial/final inversion."""
    crc = 0xFFFFFFFF
    for octet in data:
        crc ^= octet
        for _ in range(8):
            crc = (crc >> 1) ^ (CRC32_REFLECTED_POLY if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


def fcs_bytes(data: bytes) -> bytes:
    """Return the four FCS octets in line byte order."""
    return ethernet_crc32(data).to_bytes(4, "little")


def build_frame(dst: bytes, src: bytes, ethertype: int, payload: bytes) -> bytes:
    if len(dst) != 6 or len(src) != 6:
        raise ValueError("MAC addresses must contain exactly six bytes")
    if not 0 <= ethertype <= 0xFFFF:
        raise ValueError("EtherType must fit in 16 bits")
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError("payload exceeds the benchmark non-jumbo limit")
    body = dst + src + ethertype.to_bytes(2, "big")
    body += payload.ljust(MIN_PAYLOAD_BYTES, b"\x00")
    return body + fcs_bytes(body)


@dataclass(frozen=True)
class ParsedFrame:
    dst: bytes
    src: bytes
    ethertype: int
    padded_payload: bytes
    fcs_ok: bool


def parse_frame(frame: bytes) -> ParsedFrame:
    minimum = ETH_HEADER_BYTES + MIN_PAYLOAD_BYTES + FCS_BYTES
    if len(frame) < minimum:
        raise ValueError("truncated frame")
    if len(frame) > ETH_HEADER_BYTES + MAX_PAYLOAD_BYTES + FCS_BYTES:
        raise ValueError("oversized frame")
    body, observed_fcs = frame[:-4], frame[-4:]
    return ParsedFrame(
        dst=body[0:6],
        src=body[6:12],
        ethertype=int.from_bytes(body[12:14], "big"),
        padded_payload=body[14:],
        fcs_ok=observed_fcs == fcs_bytes(body),
    )


def pause_quanta(frame: bytes) -> int | None:
    """Decode the benchmark's IEEE-compatible MAC-control pause payload."""
    parsed = parse_frame(frame)
    payload = parsed.padded_payload
    if parsed.ethertype != 0x8808 or payload[:2] != b"\x00\x01":
        return None
    return int.from_bytes(payload[2:4], "big")
