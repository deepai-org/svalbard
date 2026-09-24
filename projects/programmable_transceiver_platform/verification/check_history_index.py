"""Verify every archived artifact against its immutable local Git object."""
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    project = Path(__file__).resolve().parents[1]
    repository = project.parents[1]
    index = json.loads((project / 'evidence/history-index.json').read_text())
    seen = set()
    for row in index['reports']:
        path = Path(row['path'])
        if path.is_absolute() or '..' in path.parts or row['path'] in seen:
            raise ValueError(f'Invalid or duplicate archived path: {path}')
        seen.add(row['path'])
        commit = row.get('recovery_commit', index['recovery_commit'])
        git_path = (project / path).relative_to(repository).as_posix()
        content = subprocess.check_output(['git', 'show', f'{commit}:{git_path}'], cwd=repository)
        if len(content) != row['bytes'] or hashlib.sha256(content).hexdigest() != row['sha256']:
            raise ValueError(f'Archived content differs: {path}')
    print(f'Verified {len(seen)} unique archived artifacts against Git hashes and sizes')


if __name__ == '__main__':
    main()
