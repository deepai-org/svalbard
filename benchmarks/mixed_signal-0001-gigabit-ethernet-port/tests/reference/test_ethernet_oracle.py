#!/usr/bin/env python3
"""Self-tests for the independent MAC oracle; runnable without pytest."""

from ethernet_oracle import build_frame, ethernet_crc32, fcs_bytes, parse_frame, pause_quanta


def main() -> None:
    assert ethernet_crc32(b"123456789") == 0xCBF43926
    assert fcs_bytes(b"123456789") == bytes.fromhex("2639f4cb")

    dst = bytes.fromhex("0180c2000001")
    src = bytes.fromhex("020000000001")
    short = build_frame(dst, src, 0x0800, b"abc")
    assert len(short) == 64
    parsed = parse_frame(short)
    assert parsed.dst == dst and parsed.src == src
    assert parsed.ethertype == 0x0800 and parsed.fcs_ok
    assert parsed.padded_payload[:3] == b"abc"
    assert parsed.padded_payload[3:] == bytes(43)

    damaged = bytearray(short)
    damaged[20] ^= 0x01
    assert not parse_frame(bytes(damaged)).fcs_ok

    payload = bytes((index * 37 + 11) & 0xFF for index in range(1500))
    maximum = build_frame(dst, src, 0x88B5, payload)
    assert len(maximum) == 1518
    assert parse_frame(maximum).padded_payload == payload

    pause = build_frame(dst, src, 0x8808, b"\x00\x01\x12\x34")
    assert pause_quanta(pause) == 0x1234
    assert pause_quanta(short) is None

    try:
        parse_frame(b"too short")
    except ValueError:
        pass
    else:
        raise AssertionError("truncated frames must be rejected")

    print("ethernet oracle self-test: PASS")


if __name__ == "__main__":
    main()
