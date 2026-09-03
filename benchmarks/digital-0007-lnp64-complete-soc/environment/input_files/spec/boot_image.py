#!/usr/bin/env python3
"""Executable definition of the LNP64 boot image and UART framing."""

from __future__ import annotations

import struct
import zlib

MAGIC = b"LNP64IMG"
UART_SYNC = b"LNPB"
VERSION = 1
HEADER = struct.Struct("<8sIIQQQQIIII")
PAGE_BYTES = 4096


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFF_FFFF


def build_image(
    payload: bytes,
    load_address: int,
    entry: int,
    flags: int = 0,
    exec_bytes: int | None = None,
    bss_bytes: int = 0,
) -> bytes:
    if not payload:
        raise ValueError("payload must not be empty")
    if flags != 0:
        raise ValueError("version 1 defines no flags")
    if entry & 7:
        raise ValueError("entry must be 8-byte aligned")
    if exec_bytes is None:
        exec_bytes = len(payload)
    if load_address % PAGE_BYTES or not 0 < exec_bytes <= min(len(payload), 0xFFFF_FFFF):
        raise ValueError("invalid executable segment")
    if (exec_bytes != len(payload) or bss_bytes) and exec_bytes % PAGE_BYTES:
        raise ValueError("writable segment must start on a page boundary")
    if not 0 <= bss_bytes <= 0xFFFF_FFFF:
        raise ValueError("invalid BSS length")
    if not load_address <= entry < load_address + exec_bytes:
        raise ValueError("entry outside executable segment")
    header = HEADER.pack(
        MAGIC, VERSION, HEADER.size, len(payload), load_address, entry, flags,
        crc32(payload), exec_bytes, bss_bytes, 0,
    )
    return header + payload


def parse_image(image: bytes, allowed_start: int, allowed_end: int) -> dict[str, int | bytes]:
    if len(image) < HEADER.size:
        raise ValueError("truncated header")
    fields = HEADER.unpack_from(image)
    magic, version, header_size, size, load, entry, flags, expected_crc, exec_bytes, bss_bytes, reserved = fields
    if magic != MAGIC or version != VERSION or header_size != HEADER.size or reserved != 0:
        raise ValueError("invalid header")
    if size == 0 or flags != 0:
        raise ValueError("invalid version 1 image options")
    payload = image[HEADER.size:]
    if len(payload) != size:
        raise ValueError("invalid image length")
    image_end = load + size + bss_bytes
    mapped_end = (image_end + PAGE_BYTES - 1) & -PAGE_BYTES
    if load % PAGE_BYTES or image_end < load or load < allowed_start or mapped_end > allowed_end:
        raise ValueError("image outside executable memory")
    if not 0 < exec_bytes <= size or ((exec_bytes != size or bss_bytes) and exec_bytes % PAGE_BYTES):
        raise ValueError("invalid executable segment")
    if entry & 7 or not (load <= entry < load + exec_bytes):
        raise ValueError("invalid entry")
    if crc32(payload) != expected_crc:
        raise ValueError("CRC mismatch")
    return {
        "payload": payload, "load_address": load, "entry": entry, "flags": flags,
        "exec_bytes": exec_bytes, "bss_bytes": bss_bytes,
    }


def frame_uart(image: bytes) -> bytes:
    if len(image) > 0xFFFF_FFFF:
        raise ValueError("UART image exceeds u32 framing")
    return UART_SYNC + struct.pack("<I", len(image)) + image + struct.pack("<I", crc32(image))


def parse_uart(frame: bytes) -> bytes:
    if len(frame) < 12 or frame[:4] != UART_SYNC:
        raise ValueError("invalid UART frame")
    size = struct.unpack_from("<I", frame, 4)[0]
    if len(frame) != 8 + size + 4:
        raise ValueError("invalid UART frame length")
    image = frame[8:8 + size]
    if crc32(image) != struct.unpack_from("<I", frame, 8 + size)[0]:
        raise ValueError("UART CRC mismatch")
    return image
