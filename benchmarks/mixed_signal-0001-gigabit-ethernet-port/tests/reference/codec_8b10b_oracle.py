"""Dependency-free 8b/10b and fixed-link ordered-set oracle.

The table construction follows LiteX ``code_8b10b.py`` and the ordered symbols
follow LiteEth ``pcs_1000basex.py``.  Both upstream projects are BSD-2-Clause;
exact revisions and attribution are recorded in ``THIRD_PARTY.md``.  This file
is an independent behavioral oracle, not candidate RTL.

Words returned by :func:`encode` use the benchmark wire convention: integer bit
0 is transmitted first.  ``running_disparity=False`` means negative disparity;
``True`` means positive disparity.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

TABLE_5B6B = (
    0b011000, 0b100010, 0b010010, 0b110001, 0b001010, 0b101001, 0b011001, 0b000111,
    0b000110, 0b100101, 0b010101, 0b110100, 0b001101, 0b101100, 0b011100, 0b101000,
    0b100100, 0b100011, 0b010011, 0b110010, 0b001011, 0b101010, 0b011010, 0b000101,
    0b001100, 0b100110, 0b010110, 0b001001, 0b001110, 0b010001, 0b100001, 0b010100,
)
TABLE_3B4B = (0b0100, 0b1001, 0b0101, 0b0011, 0b0010, 0b1010, 0b0110, 0b0001)
LEGAL_K = frozenset(
    [((y << 5) | 28) for y in range(8)]
    + [((7 << 5) | x) for x in (23, 27, 29, 30)]
)


class InvalidSymbol(ValueError):
    pass


class InvalidCode(ValueError):
    pass


class DisparityError(InvalidCode):
    pass


@dataclass(frozen=True)
class Symbol:
    value: int
    control: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 0xFF:
            raise InvalidSymbol("symbol value must fit in one octet")
        if self.control and self.value not in LEGAL_K:
            raise InvalidSymbol(f"illegal K character: 0x{self.value:02x}")


@dataclass(frozen=True)
class Decoded:
    symbol: Symbol
    running_disparity: bool


def k(x: int, y: int) -> Symbol:
    return Symbol((y << 5) | x, True)


def d(x: int, y: int) -> Symbol:
    return Symbol((y << 5) | x, False)


def _disparity(word: int, width: int) -> int:
    ones = sum((word >> bit) & 1 for bit in range(width))
    return ones - (width - ones)


def _reverse_bits(word: int, width: int) -> int:
    return sum(((word >> bit) & 1) << (width - 1 - bit) for bit in range(width))


def encode(symbol: Symbol, running_disparity: bool, *, wire_order: bool = True) -> tuple[int, bool]:
    """Encode one legal symbol and return ``(ten_bit_word, next_rd)``."""
    code5 = symbol.value & 0x1F
    code3 = symbol.value >> 5

    if symbol.control and code5 == 28:
        code6 = 0b110000
        code6_unbalanced = True
        code6_flip = True
    else:
        code6 = TABLE_5B6B[code5]
        code6_unbalanced = _disparity(code6, 6) != 0
        code6_flip = code6_unbalanced or code5 == 7

    code4 = TABLE_3B4B[code3]
    code4_unbalanced = _disparity(code4, 4) != 0
    code4_flip = True if symbol.control else (code4_unbalanced or code3 == 3)

    alt7_rd_negative = code3 == 7 and (code5 in (17, 18, 20) or symbol.control)
    alt7_rd_positive = code3 == 7 and (code5 in (11, 13, 14) or symbol.control)

    intermediate_rd = running_disparity ^ code6_unbalanced
    output6 = (~code6 & 0x3F) if (not running_disparity and code6_flip) else code6

    if not intermediate_rd and alt7_rd_negative:
        next_rd = True
        output4 = 0b0111
    elif intermediate_rd and alt7_rd_positive:
        next_rd = False
        output4 = 0b1000
    else:
        next_rd = intermediate_rd ^ code4_unbalanced
        output4 = (~code4 & 0xF) if (not intermediate_rd and code4_flip) else code4

    conventional_word = (output6 << 4) | output4
    word = _reverse_bits(conventional_word, 10) if wire_order else conventional_word
    return word, next_rd


@lru_cache(maxsize=2)
def _codebooks(wire_order: bool) -> tuple[dict[tuple[bool, int], Decoded], set[int]]:
    exact: dict[tuple[bool, int], Decoded] = {}
    any_disparity: set[int] = set()
    symbols = [Symbol(value) for value in range(256)] + [Symbol(value, True) for value in sorted(LEGAL_K)]
    for rd in (False, True):
        for symbol in symbols:
            word, next_rd = encode(symbol, rd, wire_order=wire_order)
            key = (rd, word)
            previous = exact.get(key)
            if previous is not None and previous.symbol != symbol:
                raise AssertionError(f"ambiguous 8b/10b code 0x{word:03x}")
            exact[key] = Decoded(symbol, next_rd)
            any_disparity.add(word)
    return exact, any_disparity


def decode(word: int, running_disparity: bool, *, wire_order: bool = True) -> Decoded:
    if not 0 <= word < 1024:
        raise InvalidCode("code group must fit in 10 bits")
    exact, any_disparity = _codebooks(wire_order)
    decoded = exact.get((running_disparity, word))
    if decoded is not None:
        return decoded
    if word in any_disparity:
        raise DisparityError(f"code 0x{word:03x} is invalid for current running disparity")
    raise InvalidCode(f"invalid 10-bit code 0x{word:03x}")


K_COMMA = k(28, 5)
K_START = k(27, 7)
K_TERMINATE = k(29, 7)
K_EXTEND = k(23, 7)
D_IDLE_PRESERVE = d(5, 6)
D_IDLE_FLIP = d(16, 2)


def encode_sequence(symbols: Iterable[Symbol], running_disparity: bool = False) -> tuple[list[int], bool]:
    words: list[int] = []
    rd = running_disparity
    for symbol in symbols:
        word, rd = encode(symbol, rd)
        words.append(word)
    return words, rd


def idle_symbols(running_disparity: bool) -> tuple[list[Symbol], bool]:
    """Return the benchmark `/K28.5/` plus `/I1/` or `/I2/` idle pair."""
    _, after_comma = encode(K_COMMA, running_disparity)
    second = D_IDLE_PRESERVE if not after_comma else D_IDLE_FLIP
    symbols = [K_COMMA, second]
    _, final_rd = encode_sequence(symbols, running_disparity)
    return symbols, final_rd


def line_frame_symbols(frame_with_fcs: bytes) -> list[Symbol]:
    """Map one padded MAC frame+FCS to the frozen PCS packet sequence.

    `/S/` replaces the first preamble octet; six remaining ``0x55`` octets and
    the ``0xd5`` SFD precede the frame.  One `/R/` follows `/T/` in this
    benchmark profile.
    """
    if len(frame_with_fcs) < 64:
        raise ValueError("line frame must already include minimum padding and FCS")
    return (
        [K_START]
        + [Symbol(0x55) for _ in range(6)]
        + [Symbol(0xD5)]
        + [Symbol(octet) for octet in frame_with_fcs]
        + [K_TERMINATE, K_EXTEND]
    )


def recognize_line_frame(symbols: Sequence[Symbol]) -> bytes:
    if len(symbols) < 1 + 6 + 1 + 64 + 2:
        raise ValueError("truncated PCS packet")
    if symbols[0] != K_START or list(symbols[-2:]) != [K_TERMINATE, K_EXTEND]:
        raise ValueError("bad PCS packet delimiters")
    if list(symbols[1:7]) != [Symbol(0x55)] * 6 or symbols[7] != Symbol(0xD5):
        raise ValueError("bad PCS preamble/SFD")
    body = symbols[8:-2]
    if any(symbol.control for symbol in body):
        raise ValueError("control character inside frame body")
    return bytes(symbol.value for symbol in body)
