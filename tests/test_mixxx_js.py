"""Runs the generated Mixxx mapping against a small simulated Mixxx engine (needs node)."""
import shutil
import subprocess
from pathlib import Path

import pytest

from s4bridge.engine.profile import DEFAULT_PROFILE
from s4bridge.mixxx import export

SIM = Path(__file__).with_name("js") / "mixxx_sim.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_mapping_in_simulated_mixxx(tmp_path):
    xml, js = export(DEFAULT_PROFILE, tmp_path)
    r = subprocess.run(["node", str(SIM), str(xml), str(js)], capture_output=True, text=True)
    print(r.stdout)
    assert r.returncode == 0, r.stdout + r.stderr
