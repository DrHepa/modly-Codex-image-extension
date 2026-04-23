from __future__ import annotations

from pathlib import Path

from codex_backend.contracts import (
    PREFLIGHT_CODE_CODEX_MISSING,
    PREFLIGHT_CODE_NOT_AUTHENTICATED,
    PREFLIGHT_CODE_NO_ENTITLEMENT,
    PREFLIGHT_CODE_UNSUPPORTED_PLATFORM,
    PREFLIGHT_CODE_UNSUPPORTED_VERSION,
)
from codex_backend.preflight import run_preflight


def test_run_preflight_passes_for_supported_authenticated_entitled_runtime() -> None:
    report = run_preflight(
        executable="codex",
        supported_versions=("1.2.3",),
        which=lambda _: "/usr/local/bin/codex",
        runner=lambda command: type("Proc", (), {"returncode": 0, "stdout": "codex 1.2.3", "stderr": ""})(),
        platform_resolver=lambda: "Linux",
        machine_resolver=lambda: "x86_64",
        auth_detector=lambda _: ("authenticated", "entitled", None),
    )

    assert report.ok is True
    assert report.machine_code is None
    assert report.evidence.runtime_name == "codex"
    assert report.evidence.runtime_version == "1.2.3"
    assert report.evidence.auth_state == "authenticated"
    assert report.evidence.entitlement_state == "entitled"
    assert report.supported_version_range == "1.2.3"


def test_run_preflight_blocks_when_codex_is_missing() -> None:
    report = run_preflight(which=lambda _: None)

    assert report.ok is False
    assert report.machine_code == PREFLIGHT_CODE_CODEX_MISSING


def test_run_preflight_blocks_when_platform_is_unsupported() -> None:
    report = run_preflight(
        supported_versions=("1.2.3",),
        which=lambda _: "/usr/local/bin/codex",
        platform_resolver=lambda: "Linux",
        machine_resolver=lambda: "arm64",
    )

    assert report.ok is False
    assert report.machine_code == PREFLIGHT_CODE_UNSUPPORTED_PLATFORM
    assert report.evidence.platform == "linux/arm64"


def test_run_preflight_blocks_when_version_is_not_allowlisted() -> None:
    report = run_preflight(
        supported_versions=("9.9.9",),
        which=lambda _: "/usr/local/bin/codex",
        runner=lambda command: type("Proc", (), {"returncode": 0, "stdout": "codex 1.2.3", "stderr": ""})(),
        platform_resolver=lambda: "Linux",
        machine_resolver=lambda: "x86_64",
    )

    assert report.ok is False
    assert report.machine_code == PREFLIGHT_CODE_UNSUPPORTED_VERSION
    assert report.evidence.runtime_version == "1.2.3"
    assert report.supported_version_range == "9.9.9"


def test_run_preflight_blocks_when_authentication_is_missing() -> None:
    report = run_preflight(
        supported_versions=("1.2.3",),
        which=lambda _: "/usr/local/bin/codex",
        runner=lambda command: type("Proc", (), {"returncode": 0, "stdout": "codex 1.2.3", "stderr": ""})(),
        platform_resolver=lambda: "Linux",
        machine_resolver=lambda: "x86_64",
        auth_detector=lambda _: ("unauthenticated", "entitled", "login required"),
    )

    assert report.ok is False
    assert report.machine_code == PREFLIGHT_CODE_NOT_AUTHENTICATED
    assert report.reason == "login required"


def test_run_preflight_blocks_when_entitlement_is_missing() -> None:
    report = run_preflight(
        supported_versions=("1.2.3",),
        which=lambda _: "/usr/local/bin/codex",
        runner=lambda command: type("Proc", (), {"returncode": 0, "stdout": "codex 1.2.3", "stderr": ""})(),
        platform_resolver=lambda: "Darwin",
        machine_resolver=lambda: "arm64",
        auth_detector=lambda _: ("authenticated", "free", "unsupported plan"),
    )

    assert report.ok is False
    assert report.machine_code == PREFLIGHT_CODE_NO_ENTITLEMENT
    assert report.reason == "unsupported plan"
