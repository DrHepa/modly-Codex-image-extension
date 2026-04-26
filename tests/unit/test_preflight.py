from __future__ import annotations

from pathlib import Path

from codex_backend.contracts import (
    PREFLIGHT_CODE_CODEX_MISSING,
    PREFLIGHT_CODE_NOT_AUTHENTICATED,
    PREFLIGHT_CODE_NO_ENTITLEMENT,
    PREFLIGHT_CODE_UNSUPPORTED_PLATFORM,
    PREFLIGHT_CODE_UNSUPPORTED_VERSION,
)
from codex_backend.preflight import detect_auth_states, run_preflight


def _successful_version_runner(command):
    return type("Proc", (), {"returncode": 0, "stdout": "codex 0.124.0", "stderr": ""})()


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


def test_run_preflight_uses_default_minimum_when_env_is_not_set(monkeypatch) -> None:
    monkeypatch.delenv("CODEX_SUPPORTED_VERSIONS", raising=False)
    monkeypatch.delenv("CODEX_MIN_SUPPORTED_VERSION", raising=False)

    report = run_preflight(
        executable="codex",
        which=lambda _: "/usr/local/bin/codex",
        runner=lambda command: type("Proc", (), {"returncode": 0, "stdout": "codex 0.122.0", "stderr": ""})(),
        platform_resolver=lambda: "Linux",
        machine_resolver=lambda: "arm64",
        auth_detector=lambda _: ("authenticated", "entitled", None),
    )

    assert report.ok is True
    assert report.supported_version_range == ">= 0.122.0"


def test_run_preflight_accepts_newer_codex_from_default_minimum(monkeypatch) -> None:
    monkeypatch.delenv("CODEX_SUPPORTED_VERSIONS", raising=False)
    monkeypatch.delenv("CODEX_MIN_SUPPORTED_VERSION", raising=False)

    report = run_preflight(
        executable="codex",
        which=lambda _: "/usr/local/bin/codex",
        runner=lambda command: type("Proc", (), {"returncode": 0, "stdout": "codex 0.125.0", "stderr": ""})(),
        platform_resolver=lambda: "Linux",
        machine_resolver=lambda: "arm64",
        auth_detector=lambda _: ("authenticated", "entitled", None),
    )

    assert report.ok is True
    assert report.machine_code is None
    assert report.evidence.runtime_version == "0.125.0"
    assert report.supported_version_range == ">= 0.122.0"


def test_run_preflight_blocks_below_default_minimum(monkeypatch) -> None:
    monkeypatch.delenv("CODEX_SUPPORTED_VERSIONS", raising=False)
    monkeypatch.delenv("CODEX_MIN_SUPPORTED_VERSION", raising=False)

    report = run_preflight(
        executable="codex",
        which=lambda _: "/usr/local/bin/codex",
        runner=lambda command: type("Proc", (), {"returncode": 0, "stdout": "codex 0.121.9", "stderr": ""})(),
        platform_resolver=lambda: "Linux",
        machine_resolver=lambda: "arm64",
        auth_detector=lambda _: ("authenticated", "entitled", None),
    )

    assert report.ok is False
    assert report.machine_code == PREFLIGHT_CODE_UNSUPPORTED_VERSION
    assert report.evidence.runtime_version == "0.121.9"
    assert report.supported_version_range == ">= 0.122.0"


def test_run_preflight_env_supported_versions_keeps_strict_exact_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("CODEX_SUPPORTED_VERSIONS", "0.124.0")

    report = run_preflight(
        executable="codex",
        which=lambda _: "/usr/local/bin/codex",
        runner=lambda command: type("Proc", (), {"returncode": 0, "stdout": "codex 0.125.0", "stderr": ""})(),
        platform_resolver=lambda: "Linux",
        machine_resolver=lambda: "arm64",
        auth_detector=lambda _: ("authenticated", "entitled", None),
    )

    assert report.ok is False
    assert report.machine_code == PREFLIGHT_CODE_UNSUPPORTED_VERSION
    assert report.evidence.runtime_version == "0.125.0"
    assert report.supported_version_range == "0.124.0"


def test_run_preflight_allows_experimental_windows_amd64_when_existing_gates_pass() -> None:
    report = run_preflight(
        executable="codex",
        which=lambda _: r"C:\\Tools\\codex.cmd",
        runner=_successful_version_runner,
        platform_resolver=lambda: "Windows",
        machine_resolver=lambda: "AMD64",
        auth_detector=lambda _: ("authenticated", "entitled", None),
    )

    assert report.ok is True
    assert report.machine_code is None
    assert report.evidence.platform == "windows/x86_64"
    assert report.evidence.runtime_version == "0.124.0"


def test_run_preflight_normalizes_windows_x86_64_aliases() -> None:
    observed_platforms = []
    for machine in ("x86_64", "x64"):
        report = run_preflight(
            executable="codex",
            which=lambda _: r"C:\\Tools\\codex.exe",
            runner=_successful_version_runner,
            platform_resolver=lambda: "Windows",
            machine_resolver=lambda machine=machine: machine,
            auth_detector=lambda _: ("authenticated", "entitled", None),
        )
        assert report.ok is True
        observed_platforms.append(report.evidence.platform)

    assert observed_platforms == ["windows/x86_64", "windows/x86_64"]


def test_run_preflight_blocks_windows_aarch64_alias_as_unsupported() -> None:
    report = run_preflight(
        executable="codex",
        which=lambda _: r"C:\\Tools\\codex.exe",
        runner=_successful_version_runner,
        platform_resolver=lambda: "Windows",
        machine_resolver=lambda: "aarch64",
        auth_detector=lambda _: ("authenticated", "entitled", None),
    )

    assert report.ok is False
    assert report.machine_code == PREFLIGHT_CODE_UNSUPPORTED_PLATFORM
    assert report.evidence.platform == "windows/arm64"


def test_run_preflight_allows_linux_arm64_for_current_host_preview_path() -> None:
    report = run_preflight(
        executable="codex",
        supported_versions=("1.2.3",),
        which=lambda _: "/usr/local/bin/codex",
        runner=lambda command: type("Proc", (), {"returncode": 0, "stdout": "codex 1.2.3", "stderr": ""})(),
        platform_resolver=lambda: "Linux",
        machine_resolver=lambda: "arm64",
        auth_detector=lambda _: ("authenticated", "entitled", None),
    )

    assert report.ok is True
    assert report.machine_code is None
    assert report.evidence.platform == "linux/arm64"


def test_run_preflight_blocks_when_codex_is_missing() -> None:
    report = run_preflight(which=lambda _: None)

    assert report.ok is False
    assert report.machine_code == PREFLIGHT_CODE_CODEX_MISSING


def test_run_preflight_blocks_when_platform_is_unsupported() -> None:
    report = run_preflight(
        supported_versions=("1.2.3",),
        which=lambda _: "/usr/local/bin/codex",
        platform_resolver=lambda: "Linux",
        machine_resolver=lambda: "ppc64le",
    )

    assert report.ok is False
    assert report.machine_code == PREFLIGHT_CODE_UNSUPPORTED_PLATFORM
    assert report.evidence.platform == "linux/ppc64le"


def test_run_preflight_keeps_windows_arm64_unsupported() -> None:
    report = run_preflight(
        which=lambda _: r"C:\\Tools\\codex.exe",
        platform_resolver=lambda: "Windows",
        machine_resolver=lambda: "ARM64",
    )

    assert report.ok is False
    assert report.machine_code == PREFLIGHT_CODE_UNSUPPORTED_PLATFORM
    assert report.evidence.platform == "windows/arm64"
    assert "windows/arm64" in report.reason


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


def test_detect_auth_states_accepts_login_status_chatgpt_output() -> None:
    seen_commands: list[tuple[str, ...]] = []

    def runner(command):
        seen_commands.append(tuple(command))
        if command[:3] == ["codex", "login", "status"]:
            return type("Proc", (), {"returncode": 0, "stdout": "Logged in using ChatGPT", "stderr": ""})()
        return type("Proc", (), {"returncode": 1, "stdout": "", "stderr": "unsupported"})()

    auth_state, entitlement_state, reason = detect_auth_states(runner=runner)

    assert auth_state == "authenticated"
    assert entitlement_state == "entitled"
    assert reason is None
    assert seen_commands[0] == ("codex", "login", "status", "--json")
