"""Shared SPICE include traversal for simulation provenance.

Mutates the caller-owned path set; preserves legacy .lib section handling.
"""
import re
from pathlib import Path

def dependencies(text,parent,paths):
 for line in text.splitlines():
  match=re.match(r'\s*\.(?:include|inc|lib)\s+(\S+)',line,re.I)
  if not match:continue
  name=match.group(1).strip('"\'')
  candidate=Path(name)
  if not candidate.is_absolute():candidate=parent/candidate
  if not candidate.is_file():
   # .lib section declarations have a bare section name, not a file.
   assert line.lower().lstrip().startswith('.lib ') and len(line.split())==2, line
   continue
  candidate=candidate.resolve()
  if candidate in paths:continue
  paths.add(candidate);dependencies(candidate.read_text(),candidate.parent,paths)
