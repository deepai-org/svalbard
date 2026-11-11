#!/usr/bin/env python3
"""Reference IEEE 802.3 clause 36 / Widmer-Franaszek 8b/10b code (IX-2 on-chip line code offload).

Bit order: a code group abcdei fghj is transmitted a first; in the transport (word 0 earliest,
bit 0 first on the line) the ten-bit symbol is bit0=a .. bit5=i, bit6=f .. bit9=j. The decoded
symbol is 9 bits {K, HGFEDCBA} (bit 8 = K). Invalid code groups decode to {K=1, 0x00}, which is
not a valid control character.
"""
D6 = {  # EDCBA -> (abcdei for RD-, abcdei for RD+)
 0:('100111','011000'),1:('011101','100010'),2:('101101','010010'),3:('110001','110001'),
 4:('110101','001010'),5:('101001','101001'),6:('011001','011001'),7:('111000','000111'),
 8:('111001','000110'),9:('100101','100101'),10:('010101','010101'),11:('110100','110100'),
 12:('001101','001101'),13:('101100','101100'),14:('011100','011100'),15:('010111','101000'),
 16:('011011','100100'),17:('100011','100011'),18:('010011','010011'),19:('110010','110010'),
 20:('001011','001011'),21:('101010','101010'),22:('011010','011010'),23:('111010','000101'),
 24:('110011','001100'),25:('100110','100110'),26:('010110','010110'),27:('110110','001001'),
 28:('001110','001110'),29:('101110','010001'),30:('011110','100001'),31:('101011','010100')}
K28_6 = ('001111', '110000')
D4 = {0:('1011','0100'),1:('1001','1001'),2:('0101','0101'),3:('1100','0011'),4:('1101','0010'),
      5:('1010','1010'),6:('0110','0110'),7:('1110','0001')}
A7 = ('0111', '1000')
K4 = {0:('1011','0100'),1:('0110','1001'),2:('1010','0101'),3:('1100','0011'),4:('1101','0010'),
      5:('0101','1010'),6:('1001','0110'),7:('0111','1000')}
VALID_K = {0x1C,0x3C,0x5C,0x7C,0x9C,0xBC,0xDC,0xFC,0xF7,0xFB,0xFD,0xFE}


def disp(bits):
    return 2*bits.count('1')-len(bits)


def encode(byte, k, rd):
    """rd: -1 or +1 (running disparity before). Returns (ten-bit int with bit0=a, rd after)."""
    x, y = byte & 31, byte >> 5
    if k:
        assert byte in VALID_K, hex(byte)
        six = K28_6[0 if rd < 0 else 1] if x == 28 else D6[x][0 if rd < 0 else 1]
    else:
        six = D6[x][0 if rd < 0 else 1]
    rd1 = rd if disp(six) == 0 else (1 if disp(six) > 0 else -1)
    if k and x == 28:
        four = K4[y][0 if rd1 < 0 else 1]
    elif y == 7 and (k or (rd1 < 0 and x in (17, 18, 20)) or (rd1 > 0 and x in (11, 13, 14))):
        four = A7[0 if rd1 < 0 else 1]
    else:
        four = D4[y][0 if rd1 < 0 else 1]
    rd2 = rd1 if disp(four) == 0 else (1 if disp(four) > 0 else -1)
    s = six + four   # a..j
    return sum(int(c) << i for i, c in enumerate(s)), rd2


def decode_tables():
    """6b -> (EDCBA, is_k28) and 4b -> HGF dictionaries over every valid sub-block."""
    t6 = {}
    for x, (n, p) in D6.items():
        for c in (n, p):
            t6[c] = x
    t4 = {}
    for y, (n, p) in D4.items():
        for c in (n, p):
            t4[c] = y
    for c in A7:
        t4[c] = 7
    return t6, t4


def decode(sym):
    """ten-bit int (bit0=a) -> 9-bit {K, byte}; invalid -> 0x100."""
    s = ''.join(str((sym >> i) & 1) for i in range(10))
    six, four = s[:6], s[6:]
    t6, t4 = decode_tables()
    if six in K28_6:
        f = four if six == '001111' else ''.join('1' if c == '0' else '0' for c in four)
        k4r = {v[1]: y for y, v in K4.items()}   # K column after RD+ (six 001111 leaves RD+)
        if f not in k4r:
            return 0x100
        return 0x100 | (k4r[f] << 5) | 28
    if six not in t6 or four not in t4:
        return 0x100
    x, y = t6[six], t4[four]
    k = four in A7 and x in (23, 27, 29, 30)
    return (0x100 if k else 0) | (y << 5) | x


if __name__ == '__main__':
    import random
    rd = -1
    for _ in range(20000):
        k = random.random() < 0.1
        b = random.choice(sorted(VALID_K)) if k else random.randrange(256)
        sym, rd = encode(b, k, rd)
        assert decode(sym) == ((0x100 if k else 0) | b), (hex(b), k, bin(sym))
    print('LINECODE_REF_PASS')
