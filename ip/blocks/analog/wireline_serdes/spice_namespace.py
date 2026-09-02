#!/usr/bin/env python3
"""Deterministically namespace internal SPICE subcircuits for parent lowering.

This intentionally operates on a self-contained source unit.  Include
resolution belongs to the caller because only that layer knows which public
top-level identities must survive composition.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path


class NamespaceError(ValueError):
    """The source cannot be namespaced without changing its meaning."""


_SUBCKT = re.compile(r"^(\s*\.subckt\s+)(\S+)", re.IGNORECASE)
_ENDS = re.compile(r"^(\s*\.ends)(?:\s+(\S+))?", re.IGNORECASE)
_INCLUDE = re.compile(r"^\s*\.inc(?:lude)?\b", re.IGNORECASE)
_TOKEN = re.compile(r"(?<!\S)([^\s]+)(?!\S)")
_INCLUDE_PATH = re.compile(
    r"^\s*\.inc(?:lude)?\s+(?:\"([^\"]+)\"|'([^']+)'|(\S+))\s*$",
    re.IGNORECASE,
)


def resolve_includes(source: Path, root: Path,
                     virtual_root: str = "/src/") -> str:
    """Resolve a SPICE include closure once, confined beneath ``root``."""
    root = root.resolve()
    visited: set[Path] = set()
    active: set[Path] = set()

    def resolve(path: Path) -> str:
        path = path.resolve()
        if path == root or root not in path.parents:
            raise NamespaceError(f"include escapes source root: {path}")
        if path in active:
            raise NamespaceError(f"cyclic include: {path}")
        if path in visited:
            return f"* duplicate include elided: {path.relative_to(root)}\n"
        if not path.is_file():
            raise NamespaceError(f"include not found: {path}")
        visited.add(path)
        active.add(path)
        output = [f"* begin resolved include: {path.relative_to(root)}\n"]
        for number, line in enumerate(path.read_text().splitlines(keepends=True), 1):
            if not _INCLUDE.match(line):
                output.append(line)
                continue
            match = _INCLUDE_PATH.match(line.strip())
            if not match:
                raise NamespaceError(f"unsupported include at {path}:{number}")
            target = next(value for value in match.groups() if value is not None)
            if target.startswith(virtual_root):
                child = root / target[len(virtual_root):]
            else:
                child = path.parent / target
            output.append(resolve(child))
        active.remove(path)
        output.append(f"* end resolved include: {path.relative_to(root)}\n")
        return "".join(output)

    return resolve(source)


def _logical_statements(lines: list[str]) -> list[list[int]]:
    statements: list[list[int]] = []
    current: list[int] = []
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("+"):
            if not current:
                raise NamespaceError(f"orphan continuation at line {index + 1}")
            current.append(index)
            continue
        if current:
            statements.append(current)
        current = [index]
    if current:
        statements.append(current)
    return statements


def namespace_source(text: str, prefix: str,
                     public_subckts: Iterable[str] = ()) -> tuple[str, dict[str, str]]:
    """Return namespaced source and a case-normalized old-to-new name map."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", prefix):
        raise NamespaceError(f"invalid namespace prefix: {prefix!r}")
    if any(_INCLUDE.match(line) for line in text.splitlines()):
        raise NamespaceError("resolve .include directives before namespacing")

    lines = text.splitlines(keepends=True)
    definitions: dict[str, str] = {}
    for number, line in enumerate(lines, 1):
        match = _SUBCKT.match(line)
        if not match:
            continue
        original = match.group(2)
        key = original.lower()
        if key in definitions:
            raise NamespaceError(
                f"duplicate subcircuit definition {original!r} at line {number}")
        definitions[key] = original

    public = {name.lower() for name in public_subckts}
    missing = public - definitions.keys()
    if missing:
        raise NamespaceError(f"public subcircuit not defined: {sorted(missing)}")
    mapping = {
        key: (original if key in public else f"{prefix}__{original}")
        for key, original in definitions.items()
    }

    active_subckt: str | None = None
    for index, line in enumerate(lines):
        match = _SUBCKT.match(line)
        if match:
            key = match.group(2).lower()
            active_subckt = key
            lines[index] = line[:match.start(2)] + mapping[key] + line[match.end(2):]
            continue
        match = _ENDS.match(line)
        if match and active_subckt is not None:
            if match.group(2):
                key = match.group(2).lower()
                if key != active_subckt:
                    raise NamespaceError(
                        f".ends {match.group(2)!r} does not match active subcircuit")
                lines[index] = (line[:match.start(2)] + mapping[key] +
                                line[match.end(2):])
            active_subckt = None

    # Replace only the final token matching a locally defined subcircuit in
    # each X-instance statement.  Earlier tokens are terminals and may legally
    # have the same spelling as a subcircuit.
    for indexes in _logical_statements(lines):
        first = lines[indexes[0]].lstrip()
        if not first or first[0].lower() != "x":
            continue
        statement = "".join(lines[index] for index in indexes)
        matches = [match for match in _TOKEN.finditer(statement)
                   if match.group(1).lower() in mapping]
        if not matches:
            continue
        match = matches[-1]
        key = match.group(1).lower()
        replacement = mapping[key]
        rewritten = statement[:match.start(1)] + replacement + statement[match.end(1):]
        chunks = rewritten.splitlines(keepends=True)
        if len(chunks) != len(indexes):
            raise NamespaceError("namespace rewrite changed logical line count")
        for index, chunk in zip(indexes, chunks, strict=True):
            lines[index] = chunk

    return "".join(lines), mapping
