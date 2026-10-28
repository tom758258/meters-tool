"""Keep the bundled zeroconf LGPL notice aligned with the locked runtime."""

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_zeroconf_notice_matches_locked_package_version():
    lock = (REPO_ROOT / "uv.lock").read_text(encoding="utf-8")
    match = re.search(
        r'\[\[package\]\]\s*\nname = "zeroconf"\s*\nversion = "([^"]+)"',
        lock,
    )
    assert match is not None
    notice = (REPO_ROOT / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
    assert f"zeroconf {match.group(1)}" in notice
    assert "third_party/licenses/zeroconf-COPYING" in notice


def test_zeroconf_lgpl_text_is_preserved():
    license_text = (
        REPO_ROOT / "third_party" / "licenses" / "zeroconf-COPYING"
    ).read_text(encoding="utf-8")
    assert license_text.startswith("python-zeroconf is distributed under the GNU Lesser")
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in license_text
    assert "END OF TERMS AND CONDITIONS" in license_text
