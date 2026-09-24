"""Collect recursive SPICE source dependencies without changing caller provenance policy."""
import re
from pathlib import Path


def collect_sources(text, parent, paths, *, include_inc=True):
    """Extend an existing path set; tolerate only internal two-token .lib sections."""
    pattern = r'\s*\.(?:include|inc|lib)\s+(\S+)' if include_inc else r'\s*\.(?:include|lib)\s+(\S+)'

    def scan(text, parent):
        for line in text.splitlines():
            match = re.match(pattern, line, re.I)
            if not match:
                continue
            path = Path(match[1].strip(chr(34) + chr(39)))
            path = path if path.is_absolute() else parent / path
            if not path.is_file():
                assert line.lower().lstrip().startswith('.lib ') and len(line.split()) == 2
                continue
            path = path.resolve()
            if path not in paths:
                paths.add(path)
                scan(path.read_text(), path.parent)
    scan(text, parent)
