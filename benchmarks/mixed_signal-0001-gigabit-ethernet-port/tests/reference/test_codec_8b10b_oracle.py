#!/usr/bin/env python3
"""Exhaustive self-test for the frozen 8b/10b and ordered-set oracle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from codec_8b10b_oracle import (
    DisparityError,
    InvalidCode,
    InvalidSymbol,
    K_COMMA,
    K_EXTEND,
    K_START,
    K_TERMINATE,
    LEGAL_K,
    Symbol,
    decode,
    encode,
    encode_sequence,
    idle_symbols,
    line_frame_symbols,
    recognize_line_frame,
)
from ethernet_oracle import build_frame

CROSSCHECK = json.loads(
    (Path(__file__).resolve().parents[1] / "assets/8b10b_crosscheck.json").read_text(encoding="utf-8")
)


def canonical_table_bytes() -> bytes:
    table = {
        "data": {
            "negative": [encode(Symbol(value), False, wire_order=False)[0] for value in range(256)],
            "positive": [encode(Symbol(value), True, wire_order=False)[0] for value in range(256)],
        },
        "control": {
            "negative": {f"{value:02x}": encode(Symbol(value, True), False, wire_order=False)[0] for value in sorted(LEGAL_K)},
            "positive": {f"{value:02x}": encode(Symbol(value, True), True, wire_order=False)[0] for value in sorted(LEGAL_K)},
        },
    }
    return json.dumps(table, sort_keys=True, separators=(",", ":")).encode()


def main() -> None:
    observed_hash = hashlib.sha256(canonical_table_bytes()).hexdigest()
    expected_hash = CROSSCHECK["encoding_comparison"]["canonical_table_sha256"]
    assert observed_hash == expected_hash, (observed_hash, expected_hash)
    assert CROSSCHECK["encoding_comparison"] == {
        "data_entries": 512,
        "control_entries": 24,
        "mismatches": 0,
        "canonical_table_sha256": expected_hash,
    }
    assert CROSSCHECK["crosscheck_status"] == "passed"

    for rd in (False, True):
        for value in range(256):
            symbol = Symbol(value)
            wire_word, next_rd = encode(symbol, rd)
            conventional, conventional_rd = encode(symbol, rd, wire_order=False)
            assert next_rd == conventional_rd
            assert wire_word == int(f"{conventional:010b}"[::-1], 2)
            assert decode(wire_word, rd).symbol == symbol
            assert decode(wire_word, rd).running_disparity == next_rd
        for value in LEGAL_K:
            symbol = Symbol(value, True)
            word, next_rd = encode(symbol, rd)
            assert decode(word, rd).symbol == symbol
            assert decode(word, rd).running_disparity == next_rd

        # Cover all 1024 possible received code groups at each RD.  Anything
        # accepted must round-trip to the exact same wire word.
        for word in range(1024):
            try:
                decoded = decode(word, rd)
            except InvalidCode:
                continue
            rebuilt, rebuilt_rd = encode(decoded.symbol, rd)
            assert rebuilt == word
            assert rebuilt_rd == decoded.running_disparity

    # Independent published known-answer comma values in conventional notation.
    assert encode(K_COMMA, False, wire_order=False)[0] == 0b0011111010
    assert encode(K_COMMA, True, wire_order=False)[0] == 0b1100000101

    try:
        Symbol(0x00, True)
    except InvalidSymbol:
        pass
    else:
        raise AssertionError("illegal K character was accepted")

    for rd in (False, True):
        symbols, final_rd = idle_symbols(rd)
        assert symbols[0] == K_COMMA and not symbols[1].control
        _, encoded_final_rd = encode_sequence(symbols, rd)
        assert final_rd == encoded_final_rd

    dst = bytes.fromhex("0180c2000001")
    src = bytes.fromhex("020000000001")
    frame = build_frame(dst, src, 0x88B5, b"oracle")
    symbols = line_frame_symbols(frame)
    assert symbols[0] == K_START and symbols[-2:] == [K_TERMINATE, K_EXTEND]
    assert recognize_line_frame(symbols) == frame
    words, _ = encode_sequence(symbols)
    assert len(words) == len(symbols)

    malformed = list(symbols)
    malformed[0] = K_COMMA
    try:
        recognize_line_frame(malformed)
    except ValueError:
        pass
    else:
        raise AssertionError("bad start delimiter was accepted")

    malformed = list(symbols)
    malformed[2] = Symbol(0x54)
    try:
        recognize_line_frame(malformed)
    except ValueError:
        pass
    else:
        raise AssertionError("bad preamble was accepted")

    malformed = list(symbols)
    malformed[10] = K_COMMA
    try:
        recognize_line_frame(malformed)
    except ValueError:
        pass
    else:
        raise AssertionError("control character inside frame was accepted")

    # At least one legal word for the opposite RD must raise disparity, not
    # silently decode as a current-RD symbol.
    for value in range(256):
        word, _ = encode(Symbol(value), True)
        try:
            decode(word, False)
        except DisparityError:
            break
        except InvalidCode:
            continue
    else:
        raise AssertionError("disparity-error path was not exercised")

    print("8b/10b and ordered-set oracle self-test: PASS")


if __name__ == "__main__":
    main()
