"""Build the real package, exactly like makepkg / the AUR / pip would."""
import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(importlib.util.find_spec("build") is None, reason="python-build not installed")
def test_wheel_builds_and_contains_everything(tmp_path):
    r = subprocess.run([sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(tmp_path), str(ROOT)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    whl = next(tmp_path.glob("*.whl"))
    names = set(zipfile.ZipFile(whl).namelist())
    for must in ("s4bridge/app.py", "s4bridge/mixer/engine.py", "s4bridge/mixer/dsp.py",
                 "s4bridge/resources/icons/disc-3.svg", "s4bridge/resources/icons/switch-on.svg"):
        assert must in names, must
