#!/usr/bin/env python3
"""Pin the guarded OpenROAD engine and adapt LibreLane's scene-name helpers.

The base image also contains an older engine selected by its LibreLane wrapper.
Install this only in the derived digital image; design constraints stay separate.
"""
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def install():
    engine = Path('/foss/tools/openroad/bin/openroad')
    version = subprocess.check_output([str(engine), '-version'], text=True).strip()
    assert 'c74892e7b' in version, 'Unexpected engine in pinned base image: '+version
    source = Path('/usr/local/lib/python3.12/dist-packages/librelane/scripts/openroad/common/io.tcl')
    before = source.read_text()
    replacements = {
        'return [sta::scenes]': (
            'set names [list]\n'
            '            foreach scene [sta::scenes] {lappend names [get_name $scene]}\n'
            '            return $names'),
        # OpenSTA 3 set_cmd_scene takes a scene object, not its name.
        'sta::set_cmd_scene $corner_name': 'sta::set_cmd_scene [sta::find_scene $corner_name]',
        'dict set result $scene $scene': (
            'set scene_name [get_name $scene]\n'
            '                dict set result $scene_name $scene'),
    }
    after = before
    for old, new in replacements.items():
        assert after.count(old) == 1, 'LibreLane helper changed: '+old
        after = after.replace(old, new)
    source.write_text(after)
    wrapper = Path('/foss/tools/bin/librelane')
    wrapper.write_text('#!/bin/bash\nexport PATH=/foss/tools/openroad/bin:$PATH\n'
                       'exec /usr/local/bin/librelane "$@"\n')
    wrapper.chmod(0o755)
    pdk = Path('/pdk')
    assert not pdk.exists(), 'Pinned image unexpectedly already defines /pdk'
    pdk.symlink_to('/foss/pdks', target_is_directory=True)
    report = dict(
        engine=str(engine), version=version, executable_sha256=sha(engine),
        librelane_io_original_sha256=hashlib.sha256(before.encode()).hexdigest(),
        librelane_io_patched_sha256=sha(source), wrapper_sha256=sha(wrapper),
        installer_sha256=sha(__file__), pdk_alias=str(pdk.resolve()),
        scope='Tool selection and scene-name compatibility only; no constraint or circuit changes.')
    target = Path('/opt/svalbard/toolchain.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    install()
