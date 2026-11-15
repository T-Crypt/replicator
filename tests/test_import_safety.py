import os
import shutil
import subprocess
from pathlib import Path

import pytest

from replicator.core import importers

MAKE_EVIL = '''
import bpy, sys
out, marker = sys.argv[sys.argv.index("--") + 1:]
bpy.context.preferences.filepaths.use_scripts_auto_execute = True
bpy.ops.wm.save_userpref()
t = bpy.data.texts.new("evil.py")
t.use_module = True
t.write(f"open({marker!r}, 'w').write('ran')\\n")
bpy.ops.wm.save_as_mainfile(filepath=out)
'''


@pytest.mark.skipif(shutil.which("blender") is None, reason="needs Blender")
def test_an_imported_blend_never_runs_its_embedded_script(tmp_path, monkeypatch):
    monkeypatch.setenv("BLENDER_USER_CONFIG", str(tmp_path / "cfg"))     # a user who allows auto-run
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    evil, marker = tmp_path / "evil.blend", tmp_path / "pwned"
    subprocess.run(["blender", "-b", "--factory-startup", "--python-expr", MAKE_EVIL, "--", str(evil), str(marker)],
                   check=True, capture_output=True, env=os.environ.copy(), timeout=120)
    assert evil.exists() and not marker.exists()
    importers._blender(evil, tmp_path / "out.glb")
    assert (tmp_path / "out.glb").exists()
    assert not marker.exists(), "the .blend's registered text block ran during import"
