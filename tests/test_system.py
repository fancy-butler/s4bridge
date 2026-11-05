import json
import subprocess
from pathlib import Path

from s4bridge import system, updates

ROOT = Path(__file__).resolve().parent.parent


def test_builtin_udev_rule_matches_packaged_file():
    assert system.UDEV_RULE == (ROOT / "packaging" / system.RULE_NAME).read_text()


def test_udev_install_script_is_valid_shell_and_writes_the_rule(tmp_path):
    script = system.udev_install_script()
    assert subprocess.run(["sh", "-n", "-c", script]).returncode == 0
    # run the heredoc part against a temp dir to prove the rule comes out byte-identical
    part = script.split("\n", 1)[1].split("chmod")[0].replace("/etc/udev/rules.d", str(tmp_path))
    subprocess.run(["sh", "-c", part], check=True)
    assert (tmp_path / system.RULE_NAME).read_text() == system.UDEV_RULE


def test_report_has_versions_and_no_home_path(monkeypatch):
    from s4bridge import __version__

    class FakeCore:
        demo = True
        status = ("connected", f"reading {Path.home()}/x")
        settings = {"mixer_enabled": False}

    monkeypatch.setattr("s4bridge.health.run_checks", lambda core: [])
    text = system.build_report(FakeCore())
    assert __version__ in text and "Kernel" in text and "udev rule" in text
    assert str(Path.home()) not in text


def test_version_compare():
    assert updates.is_newer("0.6.0", "0.5.4")
    assert updates.is_newer("v1.0", "0.9.9")
    assert updates.is_newer("0.5.10", "0.5.9")
    assert not updates.is_newer("0.5.4", "0.5.4")
    assert not updates.is_newer("0.5.3", "0.5.4")
    assert not updates.is_newer("garbage", "0.5.4")


def test_parse_release_skips_prereleases_and_junk():
    ok = json.dumps({"tag_name": "v0.6.0", "html_url": "https://x/r"}).encode()
    assert updates.parse_release(ok) == ("0.6.0", "https://x/r")
    assert updates.parse_release(json.dumps({"tag_name": "v0.7.0", "prerelease": True}).encode()) is None
    assert updates.parse_release(b"{nope") is None
    assert updates.parse_release(b'{"message": "Not Found"}') is None


def test_update_check_is_daily_and_can_be_turned_off():
    assert updates.due({}, now=100000)
    assert not updates.due({"update_checked_at": 100000}, now=100000 + 3600)
    assert updates.due({"update_checked_at": 100000}, now=100000 + updates.INTERVAL)
    assert not updates.due({"check_updates": False}, now=10 ** 9)
