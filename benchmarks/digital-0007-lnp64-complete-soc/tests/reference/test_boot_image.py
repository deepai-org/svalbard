#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = Path("/app/input_files") if Path("/app/input_files/spec").is_dir() else ROOT / "environment/input_files"
sys.path.insert(0, str(INPUT / "spec"))
from boot_image import HEADER, build_image, frame_uart, parse_image, parse_uart  # noqa: E402


def reject(fn, *args) -> None:
    try:
        fn(*args)
    except ValueError:
        return
    raise AssertionError("invalid input was accepted")


def main() -> None:
    payload = bytes(range(256)) * 17
    image = build_image(payload, 0x40001000, 0x40001000, exec_bytes=4096, bss_bytes=8192)
    assert HEADER.size == 64
    parsed = parse_image(image, 0x40000000, 0x44000000)
    assert parsed["payload"] == payload
    assert parsed["exec_bytes"] == 4096 and parsed["bss_bytes"] == 8192
    assert parse_uart(frame_uart(image)) == image

    damaged = bytearray(image)
    damaged[-1] ^= 1
    reject(parse_image, bytes(damaged), 0x40000000, 0x44000000)
    reject(parse_image, image[:-1], 0x40000000, 0x44000000)
    reject(parse_image, image, 0x50000000, 0x54000000)
    reject(build_image, b"", 0x40001000, 0x40001000)
    reject(build_image, payload, 0x40001000, 0x40001000, 1)
    reject(build_image, payload, 0x40001001, 0x40001008)
    reject(build_image, payload, 0x40001000, 0x40001000, 0, 2048)
    reject(build_image, payload, 0x40001000, 0x40002000, 0, 4096)
    reject(parse_image, build_image(payload[:4096], 0x43fff000, 0x43fff000, bss_bytes=4096), 0x40000000, 0x44000000)
    reject(parse_uart, frame_uart(image)[:-1])
    damaged_frame = bytearray(frame_uart(image))
    damaged_frame[-1] ^= 1
    reject(parse_uart, bytes(damaged_frame))
    print("boot image oracle: PASS")


if __name__ == "__main__":
    main()
