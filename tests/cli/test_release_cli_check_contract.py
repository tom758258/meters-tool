from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_CHECK = REPO_ROOT / "scripts" / "release-cli-check.ps1"


def release_check_text() -> str:
    return RELEASE_CHECK.read_text(encoding="utf-8-sig")


def test_release_check_uses_shared_target_resolution_with_34461a_default():
    script = release_check_text()

    assert '[string]$Target = "keysight-34461a"' in script
    assert '[ValidateSet("keysight-34461a", "keysight-34460a")]' not in script
    assert "$resolvedTarget = Resolve-ValidationTarget -Target $Target" in script


def test_release_check_uses_target_aware_default_simulator_resource():
    script = release_check_text()

    assert "[string]$Resource," in script
    assert '[string]$Resource = "SIM::34461A"' not in script
    assert "if ([string]::IsNullOrWhiteSpace($Resource))" in script
    assert "$targetModel = Get-TargetCliModel -ResolvedTarget $resolvedTarget" in script
    assert '$Resource = "SIM::$targetModel"' in script
    assert '"-Resource", $Resource, "-PlanOnly"' in script
    assert '"-Target", $resolvedTarget' in script


def test_release_check_adds_stable_identity_artifact_metadata():
    script = release_check_text()

    assert "target = $resolvedTarget" in script
    assert "model_id = $resolvedTarget" in script
    assert "expected_model = $targetModel" in script
    assert '"- Model ID: $resolvedTarget"' in script
    assert '"- Expected model: $targetModel"' in script
    assert "Join-Path $releaseRoot $resolvedTarget" in script


def test_release_check_keeps_package_version_as_default_release():
    script = release_check_text()

    assert "$Release = $packageVersion" in script
    assert (
        "Release $Release does not match package version $packageVersion" in script
    )
