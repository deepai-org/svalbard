"""Shared STA text extraction; experiment-specific validity checks stay in callers."""
import re


def reported_paths(section, group=None):
    """Preserve report order; optionally select an exact path-group line."""
    paths = []
    for path in section.split('Startpoint:')[1:]:
        if group is None or 'Path Group: ' + group + '\n' in path:
            paths.append({
                'slack_ns': float(re.search(r'([-\d.]+)\s+slack', path)[1]),
                'startpoint': path.splitlines()[0].strip(),
                'endpoint': re.search(r'Endpoint: (.*)', path)[1],
            })
    return paths


def domain_group_slacks(text):
    """Minimum reported slack per domain/group; every matched domain needs paths."""
    domains = {}
    for name, body in re.findall(r'DOMAIN_BEGIN (\w+)\n(.*?)DOMAIN_END \1', text, re.S):
        groups = {}
        for block in body.split('Startpoint:')[1:]:
            group = re.search(r'Path Group: (\S+)', block)
            slack = re.search(r'(-?\d+\.\d+)\s+slack \(', block)
            if group and slack:
                groups.setdefault(group[1], []).append(float(slack[1]))
        assert groups, name
        domains[name] = {group: min(values) for group, values in groups.items()}
    return domains
