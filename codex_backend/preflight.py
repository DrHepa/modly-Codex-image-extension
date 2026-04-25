from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from typing import Callable

from .contracts import (
    PREFLIGHT_CODE_CODEX_MISSING,
    PREFLIGHT_CODE_NOT_AUTHENTICATED,
    PREFLIGHT_CODE_NO_ENTITLEMENT,
    PREFLIGHT_CODE_UNSUPPORTED_PLATFORM,
    PREFLIGHT_CODE_UNSUPPORTED_VERSION,
    PreflightReport,
    RuntimeEvidence,
)

SUPPORTED_PLATFORM_MATRIX = {
    ("darwin", "arm64"),
    ("darwin", "x86_64"),
    ("linux", "arm64"),
    ("linux", "x86_64"),
    ("windows", "x86_64"),
}
AUTHENTICATED_STATES = {"active", "authenticated", "logged_in", "ok"}
ENTITLED_STATES = {"active", "entitled", "ok", "plus", "pro", "team"}
VERSION_PATTERN = re.compile(r"(\d+(?:\.\d+){1,3})")
DEFAULT_SUPPORTED_VERSIONS = ("0.122.0", "0.124.0")


def _run_command(command: Sequence[str], *, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )


def _normalize_token(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().lower().replace("-", "_")


def _normalize_platform(system_name: str | None = None, machine_name: str | None = None) -> tuple[str, str]:
    normalized_system = (system_name or platform.system()).strip().lower()
    normalized_machine = (machine_name or platform.machine()).strip().lower()
    machine_aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "aarch64": "arm64",
    }
    return normalized_system, machine_aliases.get(normalized_machine, normalized_machine)


def _platform_label(system_name: str, machine_name: str) -> str:
    return f"{system_name}/{machine_name}"


def _load_supported_versions(explicit: Sequence[str] | None = None) -> tuple[str, ...]:
    if explicit is not None:
        return tuple(version.strip() for version in explicit if version and version.strip())

    raw = os.environ.get("CODEX_SUPPORTED_VERSIONS", "")
    env_versions = tuple(version.strip() for version in raw.split(",") if version.strip())
    return env_versions or DEFAULT_SUPPORTED_VERSIONS


def _parse_version(raw_output: str) -> str | None:
    match = VERSION_PATTERN.search(raw_output)
    if match:
        return match.group(1)

    cleaned = raw_output.strip()
    return cleaned or None


def detect_runtime_version(
    executable: str = "codex",
    *,
    runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] = _run_command,
) -> str | None:
    result = runner([executable, "--version"])
    if result.returncode != 0:
        return None
    return _parse_version(f"{result.stdout}\n{result.stderr}")


def detect_runtime_name(executable: str | None) -> str:
    if not executable:
        return "codex"
    return os.path.basename(executable) or "codex"


def _extract_states_from_mapping(payload: Mapping[str, object]) -> tuple[str | None, str | None]:
    auth_candidates = (
        payload.get("auth_state"),
        payload.get("authStatus"),
        payload.get("auth"),
        payload.get("status"),
        payload.get("login_status"),
    )
    entitlement_candidates = (
        payload.get("entitlement_state"),
        payload.get("entitlementStatus"),
        payload.get("entitlement"),
        payload.get("plan"),
        payload.get("subscription"),
        payload.get("tier"),
    )

    auth_state = next((str(value) for value in auth_candidates if value is not None), None)
    entitlement_state = next((str(value) for value in entitlement_candidates if value is not None), None)
    return auth_state, entitlement_state


def detect_auth_states(
    executable: str = "codex",
    *,
    runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] = _run_command,
    environ: Mapping[str, str] | None = None,
) -> tuple[str | None, str | None, str | None]:
    env = environ or os.environ
    env_auth = env.get("CODEX_AUTH_STATE")
    env_entitlement = env.get("CODEX_ENTITLEMENT_STATE")
    if env_auth or env_entitlement:
        return env_auth, env_entitlement, None

    commands = (
        [executable, "login", "status", "--json"],
        [executable, "login", "status"],
        [executable, "auth", "status", "--json"],
        [executable, "auth", "status"],
    )

    last_error: str | None = None
    for command in commands:
        try:
            result = runner(command)
        except Exception as exc:  # pragma: no cover - defensive boundary
            last_error = str(exc)
            continue

        if result.returncode != 0:
            last_error = (result.stderr or result.stdout or "auth status probe failed").strip()
            continue

        raw_output = (result.stdout or result.stderr or "").strip()
        if not raw_output:
            last_error = "empty auth status output"
            continue

        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, Mapping):
            auth_state, entitlement_state = _extract_states_from_mapping(parsed)
            if auth_state or entitlement_state:
                return auth_state, entitlement_state, None

        normalized_output = raw_output.lower()
        auth_state = None
        entitlement_state = None

        if "logged in" in normalized_output or "authenticated" in normalized_output:
            auth_state = "authenticated"
        elif "not logged in" in normalized_output or "unauthenticated" in normalized_output:
            auth_state = "unauthenticated"

        if "logged in using chatgpt" in normalized_output:
            entitlement_state = "entitled"
        elif any(token in normalized_output for token in ("chatgpt plus", "chatgpt pro", "entitled")):
            entitlement_state = "entitled"
        elif "no entitlement" in normalized_output or "free plan" in normalized_output:
            entitlement_state = "none"

        if auth_state or entitlement_state:
            return auth_state, entitlement_state, None

        last_error = "unable to parse auth status output"

    return None, None, last_error or "unable to verify auth or entitlement state"


def run_preflight(
    *,
    executable: str = "codex",
    supported_versions: Sequence[str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] = _run_command,
    platform_resolver: Callable[[], str] = platform.system,
    machine_resolver: Callable[[], str] = platform.machine,
    auth_detector: Callable[[str], tuple[str | None, str | None, str | None]] | None = None,
) -> PreflightReport:
    system_name, machine_name = _normalize_platform(platform_resolver(), machine_resolver())
    platform_name = _platform_label(system_name, machine_name)
    evidence = RuntimeEvidence(runtime_name="codex", platform=platform_name)

    executable_path = which(executable)
    runtime_name = detect_runtime_name(executable_path or executable)
    evidence = RuntimeEvidence(
        runtime_name=runtime_name,
        runtime_executable=executable_path or executable,
        platform=platform_name,
    )
    if not executable_path:
        return PreflightReport(
            ok=False,
            evidence=evidence,
            machine_code=PREFLIGHT_CODE_CODEX_MISSING,
            reason="Codex executable was not found on PATH.",
        )

    if (system_name, machine_name) not in SUPPORTED_PLATFORM_MATRIX:
        return PreflightReport(
            ok=False,
            evidence=evidence,
            machine_code=PREFLIGHT_CODE_UNSUPPORTED_PLATFORM,
            reason=f"Platform {platform_name} is not enabled for this V1 extension.",
        )

    runtime_version = detect_runtime_version(executable_path, runner=runner)
    evidence = RuntimeEvidence(
        runtime_name=runtime_name,
        runtime_version=runtime_version,
        runtime_executable=executable_path,
        runtime_version_source=f"{runtime_name} --version",
        platform=platform_name,
    )

    approved_versions = _load_supported_versions(supported_versions)
    supported_version_range = ", ".join(approved_versions) if approved_versions else None
    if not runtime_version or runtime_version not in approved_versions:
        return PreflightReport(
            ok=False,
            evidence=evidence,
            machine_code=PREFLIGHT_CODE_UNSUPPORTED_VERSION,
            reason=(
                "Codex runtime version is not in the approved allowlist. "
                "Set CODEX_SUPPORTED_VERSIONS or pass supported_versions explicitly."
            ),
            supported_version_range=supported_version_range,
        )

    detector = auth_detector or (lambda exe: detect_auth_states(exe, runner=runner))
    auth_state, entitlement_state, detection_reason = detector(executable_path)
    evidence = RuntimeEvidence(
        runtime_name=runtime_name,
        runtime_version=runtime_version,
        runtime_executable=executable_path,
        runtime_version_source=f"{runtime_name} --version",
        auth_state=auth_state,
        auth_reason=detection_reason,
        entitlement_state=entitlement_state,
        platform=platform_name,
    )

    normalized_auth = _normalize_token(auth_state)
    if normalized_auth not in AUTHENTICATED_STATES:
        return PreflightReport(
            ok=False,
            evidence=evidence,
            machine_code=PREFLIGHT_CODE_NOT_AUTHENTICATED,
            reason=detection_reason or "Codex authentication could not be verified.",
            supported_version_range=supported_version_range,
        )

    normalized_entitlement = _normalize_token(entitlement_state)
    if normalized_entitlement not in ENTITLED_STATES:
        return PreflightReport(
            ok=False,
            evidence=evidence,
            machine_code=PREFLIGHT_CODE_NO_ENTITLEMENT,
            reason=detection_reason or "Codex entitlement could not be verified.",
            supported_version_range=supported_version_range,
        )

    return PreflightReport(
        ok=True,
        evidence=evidence,
        supported_version_range=supported_version_range,
    )


__all__ = [
    "AUTHENTICATED_STATES",
    "DEFAULT_SUPPORTED_VERSIONS",
    "ENTITLED_STATES",
    "SUPPORTED_PLATFORM_MATRIX",
    "detect_auth_states",
    "detect_runtime_name",
    "detect_runtime_version",
    "run_preflight",
]
