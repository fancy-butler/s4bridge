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


def test_every_version_string_agrees():
    import re
    from pathlib import Path
    from s4bridge import __version__ as v
    root = Path(__file__).resolve().parent.parent
    found = {
        "pyproject.toml": re.search(r'^version = "([^"]+)"', (root / "pyproject.toml").read_text(), re.M),
        "arch PKGBUILD": re.search(r"^pkgver=(\S+)", (root / "packaging/arch/PKGBUILD").read_text(), re.M),
        "aur PKGBUILD": re.search(r"^pkgver=(\S+)", (root / "packaging/aur/PKGBUILD").read_text(), re.M),
        "fedora spec": re.search(r"^Version:\s*(\S+)", (root / "packaging/fedora/s4bridge.spec").read_text(), re.M),
        "debian changelog": re.search(r"^s4bridge \(([^)]+)\)", (root / "packaging/debian/changelog").read_text(), re.M),
        "metainfo": re.search(r'<release version="([^"]+)"',
                              next((root / "packaging").glob("*.metainfo.xml")).read_text()),
        "CHANGELOG.md": re.search(r"^## (\d+\.\d+\.\d+)", (root / "CHANGELOG.md").read_text(), re.M),
    }
    bad = {k: (m.group(1) if m else None) for k, m in found.items() if not m or m.group(1) != v}
    assert not bad, f"version {v} not matched in: {bad}"
