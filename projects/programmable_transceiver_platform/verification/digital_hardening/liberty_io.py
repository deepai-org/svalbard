#!/usr/bin/env python3
"""Minimal Liberty (.lib) reader/writer used by libchar.py.

The tree keeps every statement in order: a Group (name, args, children), a Simple attribute
(`name : value ;`) or a Complex attribute (`name (args) ;`). Values and arguments are kept as the
raw tokens of the source (quoted strings keep their quotes), so an untouched tree is written back
with identical content (whitespace and comments are not preserved).
"""
import re

_TOK = re.compile(r'"(?:[^"\\]|\\.)*"|/\*.*?\*/|//[^\n]*|\\\s*\n|[{}();:,]|[^\s{}();:,"]+', re.S)


class Simple:
    __slots__ = ('name', 'value')

    def __init__(self, name, value):
        self.name, self.value = name, value


class Complex:
    __slots__ = ('name', 'args')

    def __init__(self, name, args):
        self.name, self.args = name, args


class Group:
    __slots__ = ('name', 'args', 'children')

    def __init__(self, name, args, children=None):
        self.name, self.args, self.children = name, args, children if children is not None else []

    # helpers
    def groups(self, name=None):
        return [c for c in self.children if isinstance(c, Group) and (name is None or c.name == name)]

    def group(self, name, arg=None):
        for c in self.children:
            if isinstance(c, Group) and c.name == name and (arg is None or (c.args and unq(c.args[0]) == arg)):
                return c
        return None

    def attr(self, name, default=None):
        for c in self.children:
            if isinstance(c, Simple) and c.name == name:
                return unq(c.value)
        return default

    def set_attr(self, name, value):
        for c in self.children:
            if isinstance(c, Simple) and c.name == name:
                c.value = value
                return
        self.children.append(Simple(name, value))

    def complex(self, name):
        for c in self.children:
            if isinstance(c, Complex) and c.name == name:
                return c
        return None

    def complexes(self, name):
        return [c for c in self.children if isinstance(c, Complex) and c.name == name]


def unq(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def floats(arg):
    return [float(x) for x in unq(arg).replace('\\\n', ' ').split(',') if x.strip()]


def tokenize(text):
    for m in _TOK.finditer(text):
        t = m.group(0)
        if t.startswith('/*') or t.startswith('//') or t.startswith('\\'):
            continue
        yield t


def parse(text):
    toks = list(tokenize(text))
    pos = 0

    def stmt_list(end_brace):
        nonlocal pos
        out = []
        while pos < len(toks):
            t = toks[pos]
            if t == '}':
                if not end_brace:
                    raise ValueError('unbalanced }')
                pos += 1
                return out
            if t == ';':
                pos += 1
                continue
            name = t
            pos += 1
            nt = toks[pos]
            if nt == ':':
                pos += 1
                vals = []
                while toks[pos] != ';' and toks[pos] != '}':
                    vals.append(toks[pos])
                    pos += 1
                if toks[pos] == ';':
                    pos += 1
                out.append(Simple(name, ' '.join(vals)))
            elif nt == '(':
                pos += 1
                args, cur = [], []
                while toks[pos] != ')':
                    if toks[pos] == ',':
                        args.append(' '.join(cur))
                        cur = []
                    else:
                        cur.append(toks[pos])
                    pos += 1
                if cur:
                    args.append(' '.join(cur))
                pos += 1
                if pos < len(toks) and toks[pos] == '{':
                    pos += 1
                    out.append(Group(name, args, stmt_list(True)))
                else:
                    if pos < len(toks) and toks[pos] == ';':
                        pos += 1
                    out.append(Complex(name, args))
            else:
                raise ValueError(f'unexpected token after {name!r}: {nt!r}')
        if end_brace:
            raise ValueError('missing }')
        return out

    top = stmt_list(False)
    if len(top) != 1 or not isinstance(top[0], Group):
        raise ValueError('expected a single library group')
    return top[0]


def write(node, fh, ind=0):
    sp = '  ' * ind
    if isinstance(node, Simple):
        fh.write(f'{sp}{node.name} : {node.value} ;\n')
    elif isinstance(node, Complex):
        if node.name == 'values' and len(node.args) > 1:
            inner = (', \\\n' + sp + '  ').join(node.args)
            fh.write(f'{sp}values({inner});\n')
        else:
            fh.write(f'{sp}{node.name}({", ".join(node.args)});\n')
    else:
        fh.write(f'{sp}{node.name}({", ".join(node.args)}) {{\n')
        for c in node.children:
            write(c, fh, ind + 1)
        fh.write(f'{sp}}}\n')


def table(group, templates):
    """(index_1, index_2, values 2-D list) of a timing table group; indices fall back to the template."""
    tpl = templates.get(unq(group.args[0])) if group.args else None
    i1 = group.complex('index_1') or (tpl.complex('index_1') if tpl else None)
    i2 = group.complex('index_2') or (tpl.complex('index_2') if tpl else None)
    idx1 = floats(i1.args[0]) if i1 else []
    idx2 = floats(i2.args[0]) if i2 else []
    vals = [floats(a) for a in group.complex('values').args]
    return idx1, idx2, vals


def set_values(group, vals):
    group.complex('values').args = ['"' + ', '.join(f'{v:.6g}' for v in row) + '"' for row in vals]


# ---------------------------------------------------------------- boolean expressions (Liberty syntax)
def parse_bool(expr):
    """Liberty function/when string -> callable(dict pin->0/1) -> 0/1. Precedence ! > ^ > & > |."""
    s = expr.replace('"', '').strip()
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_\[\]]*|[01]|[!&|^()'*+]", s)
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else None

    def take():
        nonlocal pos
        pos += 1
        return toks[pos - 1]

    def p_or():
        a = p_and()
        while peek() in ('|', '+'):
            take()
            b = p_and()
            a = (lambda x, y: lambda e: x(e) | y(e))(a, b)
        return a

    def p_and():
        a = p_xor()
        while peek() in ('&', '*') or (peek() is not None and peek() not in ('|', '+', ')', '^', "'")):
            if peek() in ('&', '*'):
                take()
            b = p_xor()
            a = (lambda x, y: lambda e: x(e) & y(e))(a, b)
        return a

    def p_xor():
        a = p_not()
        while peek() == '^':
            take()
            b = p_not()
            a = (lambda x, y: lambda e: x(e) ^ y(e))(a, b)
        return a

    def p_not():
        if peek() == '!':
            take()
            a = p_not()
            r = lambda e, a=a: 1 - a(e)
        elif peek() == '(':
            take()
            r = p_or()
            if take() != ')':
                raise ValueError(expr)
        else:
            t = take()
            if t in ('0', '1'):
                r = lambda e, v=int(t): v
            else:
                r = lambda e, n=t: e[n]
        while peek() == "'":
            take()
            r = (lambda a: lambda e: 1 - a(e))(r)
        return r

    f = p_or()
    if pos != len(toks):
        raise ValueError(f'trailing tokens in {expr!r}')
    return f


def bool_vars(expr):
    return sorted(set(re.findall(r'[A-Za-z_][A-Za-z0-9_\[\]]*', expr.replace('"', ''))))
