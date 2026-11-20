"""Register access for bring-up software, driven by the generated map (spec/register-map.json, rtl/gen/gen_regfile.py).
Field writes are read-modify-write on a host shadow copy; commit() writes COMMIT and checks ERROR_INFO."""
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
MAP = json.loads((PROJECT/'spec/register-map.json').read_text())
FIELDS = {f['name']: f for f in MAP['fields']}
STATUS = {f['name']: f for f in MAP['status_fields']}
REGS = {r['addr']: r for r in MAP['registers']}
ID, ABI, HASH, CHIP_ID = 0x5356, 0x0003, MAP['map_hash16'], {'rf': 1, 'wired': 2}
A_ID, A_ABI, A_HASH, A_ISLAND, A_FAULT, A_RESET, A_CFGERR, A_COMMIT, A_ERRINFO = 0x00, 0x08, 0x09, 0x0A, 0x0B, 0x0D, 0x05, 0x06, 0x0C


class CommitError(Exception):
    pass


class Regs:
    """spi: object with xfer(cmd8, addr8, data16) -> 16-bit read data (abstract SPI, mode 0, 32 clocks)."""
    def __init__(self, spi, chip):
        self.spi, self.chip = spi, chip
        self.shadow = {a: r['reset'] for a, r in REGS.items()}

    def read(self, addr):
        return self.spi.xfer(0x00, addr, 0) & 0xFFFF

    def write_reg(self, addr, value):
        self.spi.xfer(0x80, addr, value & 0xFFFF)

    def set(self, **fields):
        """set(**{'core.aosc.enable': 1}): fields of the other chip are refused (D4: not stored, read 0)."""
        touched = set()
        for name, value in fields.items():
            f = FIELDS[name]
            if self.chip not in f['chips']:
                raise KeyError(f'{name} is not on pt_{self.chip}')
            if f.get('allowed') is not None and value not in f['allowed']:
                raise ValueError(f'{name}={value} not allowed {f["allowed"]}')
            for c in f['chunks']:
                m = ((1 << c['width']) - 1) << c['reg_lsb']
                v = ((value >> c['field_lsb']) & ((1 << c['width']) - 1)) << c['reg_lsb']
                self.shadow[c['addr']] = (self.shadow[c['addr']] & ~m) | v
                touched.add(c['addr'])
        for a in sorted(touched):
            self.write_reg(a, self.shadow[a])

    def commit(self):
        self.write_reg(A_COMMIT, 0x0001)
        info = self.read(A_ERRINFO) >> 8
        if info:
            err = self.read(A_CFGERR)
            self.write_reg(A_CFGERR, 0x7F)
            raise CommitError(f'commit rejected: ERROR_INFO[15:8]=0x{info:02X} CONFIG_ERROR=0x{err:02X}')

    def status(self, name):
        f = STATUS[name]
        return (self.read(f['addr']) >> f['reg_lsb']) & ((1 << f['bits']) - 1)

    def clocks(self, n_transactions):
        """SPI traffic only to clock SCLK (B54: the bandgap interlock counts SCLK)."""
        for _ in range(n_transactions):
            self.read(A_ID)
