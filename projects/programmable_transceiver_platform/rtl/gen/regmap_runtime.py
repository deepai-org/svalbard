"""Register-map semantics shared by the generator, the bench header and the tests.

This file is the reference model of the generated register file. The generator
executes it to validate the specification, and embeds a verbatim copy in
rtl/gen/pt_regmap.py so bench software needs no other file. It operates on
plain dicts {field_full_name: encoded_int} and on the data tables FIELDS,
REGISTERS, RULES, BREAK_BEFORE_MAKE, SPLIT_FIELDS, FORCED, ISLANDS and ATB_NODES.
"""

SYSTEM_ADDRESSES = {
    'ID': 0x00, 'ENABLE': 0x01, 'MODE8': 0x02, 'STATUS': 0x03, 'REJECTED': 0x04,
    'CONFIG_ERROR': 0x05, 'COMMIT': 0x06, 'VIEW': 0x07, 'ABI_VERSION': 0x08,
    'MAP_HASH': 0x09, 'ISLAND_STATUS': 0x0A, 'FAULT_STATUS': 0x0B, 'ERROR_INFO': 0x0C, 'RESET_STATUS': 0x0D,
    'RF_TRIM': 0x10, 'WIRE_TRIM': 0x11, 'CLOCK_TRIM': 0x12,
    'MEM_INDEX': 0x20, 'MEM_PLAY_I': 0x21, 'MEM_WRITE': 0x22, 'MEM_CONTROL': 0x23,
    'MEM_DONE': 0x24, 'MEM_CAPTURE_LO': 0x25, 'MEM_CAPTURE_HI': 0x26,
}
ID_VALUE = 0x5356
ABI_VERSION = 0x0003
COMMIT_CMD = 0x0001
REVERT_CMD = 0x0002
# CONFIG_ERROR (0x05) bits, write 1 to clear.
ERR_WRITE_RANGE = 1 << 0     # out-of-range field, reserved encoding or reserved bit set
ERR_ADDRESS = 1 << 1         # write to an unknown or read-only address
ERR_SPLIT_RANGE = 1 << 2     # commit: a >16-bit field is out of range
ERR_RULE = 1 << 3            # commit: illegal combination (RULES)
ERR_BREAK_BEFORE_MAKE = 1 << 4
ERR_RUNNING = 1 << 5         # commit: non-live field changed while ENABLE=1
ERR_LEGACY_LOCKED = 1 << 6   # legacy register written while ENABLE=1
# ERROR_INFO (0x0C) high byte: commit result code.
CODE_RUNNING = 0xFF
# RESET_STATUS (0x0D) bits, write 1 to clear. Both set by POR; only RST_OCCURRED by RESET_N.
RST_POR_OCCURRED = 1 << 0
RST_RESET_OCCURRED = 1 << 1


def _field(name):
    return FIELD_BY_NAME[name]


def field_ok(f, value):
    if value < 0 or value >= (1 << f['bits']):
        return False
    if f['allowed'] is not None:
        return value in f['allowed']
    return f['minimum'] <= value <= f['maximum']


def mant_exp_value(code, mb, db):
    """Value of a mant_exp code: exponent e = code >> mb, mantissa m = low mb bits.
    e = 0: m (exact small values); 1 <= e <= db - mb: (2^mb + m) << (e - 1); above: 2^db - 1."""
    e, m = code >> mb, code & ((1 << mb) - 1)
    if e == 0:
        return m
    if e > db - mb:
        return (1 << db) - 1
    return ((1 << mb) | m) << (e - 1)


def mant_exp_code(value, mb, db):
    """Nearest mant_exp code for value (ties to the smaller code); value 1 .. 2^db - 1."""
    best, code = None, 1
    while True:
        v = mant_exp_value(code, mb, db)
        if best is None or abs(v - value) < abs(best[1] - value):
            best = (code, v)
        if v >= (1 << db) - 1:
            return best[0]
        code += 1


def cond_ok(cond, cfg):
    name, op, values = cond
    v = cfg[name]
    if op == 'eq':
        return v == values[0]
    if op == 'ne':
        return v != values[0]
    if op == 'in':
        return v in values
    if op == 'nin':
        return v not in values
    raise ValueError(op)


def rule_ok(rule, cfg):
    trig = any(cond_ok(c, cfg) for c in rule['if_any']) if rule['if_any'] else True
    if rule['if_all']:
        trig = trig and all(cond_ok(c, cfg) for c in rule['if_all'])
    return (not trig) or all(cond_ok(c, cfg) for c in rule['then_all'])


def reset_config():
    return {f['name']: f['default'] for f in FIELDS}


def register_at(addr):
    return REGISTER_BY_ADDR.get(addr)


def reg_write_ok(reg, data):
    if data & ~reg['writable_mask'] & 0xFFFF:
        return False
    for name, field_lsb, width, reg_lsb in reg['chunks']:
        f = _field(name)
        if f['split'] or f['store'] is None:   # split: checked at commit; dropped: write-ignored
            continue
        if not field_ok(f, (data >> reg_lsb) & ((1 << width) - 1)):
            return False
    return True


def reg_apply(reg, data, cfg, active=None):
    """Apply an accepted register write to the shadow cfg. Direct (no-shadow) fields also take
    effect in `active` at once when it is given."""
    for name, field_lsb, width, reg_lsb in reg['chunks']:
        mask = ((1 << width) - 1) << field_lsb
        cfg[name] = ((cfg[name] & ~mask) | (((data >> reg_lsb) & ((1 << width) - 1)) << field_lsb)) & _field(name)['store_mask']
        if active is not None and _field(name).get('direct'):
            active[name] = cfg[name]


def reg_read(reg, cfg):
    value = 0
    for name, field_lsb, width, reg_lsb in reg['chunks']:
        value |= ((cfg[name] >> field_lsb) & ((1 << width) - 1)) << reg_lsb
    return value


def commit_code(shadow, active, enable):
    """0 when the commit is accepted, else the ERROR_INFO code (priority order as in RTL)."""
    if enable and any(shadow[f['name']] != active[f['name']] for f in FIELDS if not f['live']):
        return CODE_RUNNING
    for i, name in enumerate(SPLIT_FIELDS):
        if not field_ok(_field(name), shadow[name]):
            return 0xC0 + i
    for i, rule in enumerate(RULES):
        if not rule_ok(rule, shadow):
            return 1 + i
    for i, name in enumerate(BREAK_BEFORE_MAKE):
        if active[name] != 0 and shadow[name] != 0 and shadow[name] != active[name]:
            return 0x80 + i
    return 0


def commit_error_bit(code):
    if code == CODE_RUNNING:
        return ERR_RUNNING
    if code >= 0xC0:
        return ERR_SPLIT_RANGE
    if code >= 0x80:
        return ERR_BREAK_BEFORE_MAKE
    return ERR_RULE


def island_on(active, pgood):
    on = {}
    for island, bit in ISLANDS.items():
        on[island] = bool(active['debug.island_power.' + island]) and (
            bool((pgood >> bit) & 1) or bool(active['debug.pgood_override.' + island]))
    return on


def outputs(active, pgood, fault, enable=0):
    """Pad/analog-facing values: island isolation first, then fault forcing, then run-time clears
    (clear_when_running: forced 0 while ENABLE=1 and the named selector has the given code)."""
    on = island_on(active, pgood)
    # LU-02: bias-override fields paired with an island ATB node also need that island's power-good.
    ovr_pg = {}
    for node in ATB_NODES:
        if node['force'] == 'override' and node['island']:
            ovr_pg.setdefault('debug.bias_override.' + node['override'], []).append(node['island'])
    out = {}
    for f in FIELDS:
        if not all(on[i] for i in f['islands']) or not all((pgood >> ISLANDS[i]) & 1 for i in ovr_pg.get(f['name'], ())):
            out[f['name']] = 0
        elif fault and f['name'] in FORCED:
            out[f['name']] = FORCED[f['name']]
        else:
            out[f['name']] = active[f['name']]
        cw = f.get('clear_when_running')
        if cw and enable and active[cw[0]] == cw[1]:
            out[f['name']] = 0
    for f in FIELDS:
        if f.get('gate_and'):
            out[f['name']] = out[f['name']] if out[f['gate_and']] else 0   # multi-bit fields: all bits gated
    buses = {'analog': 0, 'debug': 0}
    for f in FIELDS:
        if f['bus'] is not None:
            v = out[f['name']] >> f['store'][1]
            if f.get('decode') == 'thermometer':
                v = (1 << v) - 1
            elif f.get('decode') == 'mant_exp':
                v = mant_exp_value(v, f['mantissa_bits'], f['decoded_bits'])
            buses[f['bus']] |= v << f['bus_lsb']
    atb = [0, 0]
    for node in ATB_NODES:
        for bus in (0, 1):
            if out['debug.atb.atb%d' % bus] == node['code'] and (node['island'] is None or (
                    on[node['island']] and (pgood >> ISLANDS[node['island']]) & 1)):
                atb[bus] |= 1 << (node['code'] - 1)
    grp = {}
    for bus in (0, 1):
        g = 0
        for gi, group in enumerate(ATB_GROUPS[f'atb{bus}']):
            if any((atb[bus] >> (c - 1)) & 1 for c in group['codes']):
                g |= 1 << gi
        grp[bus] = g
    island_en = sum(active['debug.island_power.' + i] << b for i, b in ISLANDS.items())
    island_bits = sum(int(on[i]) << b for i, b in ISLANDS.items())
    return dict(fields=out, analog_cfg=buses['analog'], debug_cfg=buses['debug'], atb0_sw=atb[0],
                atb1_sw=atb[1], atb0_grp=grp[0], atb1_grp=grp[1], island_en=island_en, island_on=island_bits)


def gray_to_binary(g):
    b = 0
    while g:
        b ^= g
        g >>= 1
    return b


def status_read(addr, inputs):
    """Read value of a read-only status register; inputs maps port name -> raw source value."""
    value = None
    for sf in STATUS_FIELDS:
        if sf['addr'] == addr and not sf.get('reserved'):
            raw = inputs.get(sf['port'], 0) & ((1 << sf['bits']) - 1)
            v = gray_to_binary(raw) if sf['encoding'] == 'gray' else raw
            value = (value or 0) | (v << sf['reg_lsb'])
    return value
