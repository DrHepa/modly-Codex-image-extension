from __future__ import annotations

from pathlib import Path

import generator as generator_module
from codex_backend.contracts import (
    PREFLIGHT_CODE_CODEX_MISSING,
    PREFLIGHT_CODE_NOT_AUTHENTICATED,
    PREFLIGHT_CODE_NO_ENTITLEMENT,
    PREFLIGHT_CODE_UNSUPPORTED_PLATFORM,
    PREFLIGHT_CODE_UNSUPPORTED_VERSION,
    PreflightReport,
    RuntimeEvidence,
)


LOCKED_DIAGNOSTIC_KEYS = {
    "runtime_source",
    "runtime_name",
    "runtime_version",
    "runtime_version_supported",
    "supported_versions",
    "platform_supported",
    "platform_key",
    "auth_state",
    "entitlement_state",
    "extension_setup_state",
    "extension_import_state",
    "codex_app_server_state",
    "readiness_source",
    "diagnostic_status",
    "last_checked_at",
}

GENERIC_ACTION_KINDS = {"show_guidance", "show_details", "open_external_url", "refresh_readiness", "repair_extension"}


def readiness_from(report: PreflightReport, monkeypatch) -> dict[str, object]:  # noqa: ANN001
    monkeypatch.setattr(generator_module, "run_preflight", lambda: report)
    adapter = generator_module.CodexImageGenerator(Path("/tmp/model"), Path("/tmp/workspace"))
    return adapter.readiness_status()


def assert_generic_actions(status: dict[str, object]) -> list[dict[str, object]]:
    actions = status["actions"]
    assert isinstance(actions, list)
    assert 1 <= len(actions) <= 5
    for action in actions:
        assert action["kind"] in GENERIC_ACTION_KINDS
        assert action["safety"] in {"manual", "non_destructive", "confirm"}
        assert "repair_extension" != action["kind"]
    return actions


def assert_locked_sanitized_diagnostics(status: dict[str, object]) -> dict[str, str]:
    details = status["details"]
    assert isinstance(details, dict)
    diagnostics = details["diagnostics"]
    assert isinstance(diagnostics, dict)
    assert set(diagnostics) <= LOCKED_DIAGNOSTIC_KEYS
    serialized = repr(status)
    assert "/home/example" not in serialized
    assert "CODEX_TOKEN" not in serialized
    assert "secret" not in serialized
    assert "raw command output" not in serialized
    return diagnostics


def test_generator_class_keeps_node_specific_schema_on_runner_start() -> None:
    assert generator_module.CodexImageGenerator.params_schema() == []


def test_generator_readiness_status_maps_preflight_machine_codes(monkeypatch) -> None:  # noqa: ANN001
    reports = iter(
        (
            PreflightReport(
                ok=False,
                machine_code=PREFLIGHT_CODE_CODEX_MISSING,
                reason="Codex executable was not found on PATH.",
                evidence=RuntimeEvidence(runtime_name="codex", platform="linux/arm64"),
            ),
            PreflightReport(
                ok=False,
                machine_code=PREFLIGHT_CODE_NOT_AUTHENTICATED,
                reason="login required",
                evidence=RuntimeEvidence(runtime_name="codex", runtime_version="0.122.0", auth_state="unauthenticated"),
            ),
            PreflightReport(
                ok=False,
                machine_code=PREFLIGHT_CODE_UNSUPPORTED_VERSION,
                reason="version is not allowlisted",
                evidence=RuntimeEvidence(runtime_name="codex", runtime_version="9.9.9"),
            ),
            PreflightReport(
                ok=True,
                evidence=RuntimeEvidence(runtime_name="codex", runtime_version="0.122.0", auth_state="authenticated"),
            ),
        )
    )
    monkeypatch.setattr(generator_module, "run_preflight", lambda: next(reports))

    adapter = generator_module.CodexImageGenerator(Path("/tmp/model"), Path("/tmp/workspace"))

    assert adapter.readiness_status()["label_hint"] == "Setup Codex"
    assert adapter.readiness_status()["label_hint"] == "Login"
    assert adapter.readiness_status()["label_hint"] == "Update Codex"
    ready_status = adapter.readiness_status()
    assert ready_status["ok"] is True
    assert ready_status["machine_code"] == "ready"
    assert ready_status["label_hint"] == "Ready"


def test_generator_readiness_status_is_read_only_and_sanitizes_evidence(monkeypatch) -> None:  # noqa: ANN001
    calls: list[str] = []

    def fake_preflight() -> PreflightReport:
        calls.append("preflight")
        return PreflightReport(
            ok=False,
            machine_code=PREFLIGHT_CODE_NOT_AUTHENTICATED,
            reason="login required",
            evidence=RuntimeEvidence(
                runtime_name="codex",
                runtime_version="0.122.0",
                runtime_executable="/home/example/.local/bin/codex",
                runtime_version_source="raw command output: token=secret",
                auth_state="unauthenticated",
                auth_reason="CODEX_TOKEN=secret from environment",
                entitlement_state="unknown",
                platform="linux/arm64",
            ),
        )

    def forbidden_generate(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("readiness_status must not generate or mutate runtime state")

    monkeypatch.setattr(generator_module, "run_preflight", fake_preflight)
    monkeypatch.setattr(generator_module, "generate", forbidden_generate)

    adapter = generator_module.CodexImageGenerator(Path("/tmp/model"), Path("/tmp/workspace"))
    status = adapter.readiness_status()

    assert calls == ["preflight"]
    assert status["ok"] is False
    assert status["machine_code"] == PREFLIGHT_CODE_NOT_AUTHENTICATED
    assert status["label_hint"] == "Login"
    assert status["evidence"] == {
        "source": "local-codex-command",
        "runtime_name": "codex",
        "runtime_version": "0.122.0",
        "auth_state": "unauthenticated",
        "entitlement_state": "unknown",
        "platform": "linux/arm64",
    }


def test_readiness_status_returns_setup_guidance_action_for_missing_codex(monkeypatch) -> None:  # noqa: ANN001
    status = readiness_from(
        PreflightReport(
            ok=False,
            machine_code=PREFLIGHT_CODE_CODEX_MISSING,
            reason="Codex executable was not found on PATH.",
            evidence=RuntimeEvidence(runtime_name="codex", platform="linux/x86_64"),
        ),
        monkeypatch,
    )

    actions = assert_generic_actions(status)
    assert status["label_hint"] == "Setup Codex"
    assert actions[0] == {
        "id": "codex.setup.guidance",
        "kind": "show_guidance",
        "label": "Setup Codex",
        "safety": "manual",
        "guidance": "Install or expose the Codex CLI on PATH using official Codex setup guidance, then refresh readiness. Modly does not run package-manager commands.",
        "docs_url": "https://developers.openai.com/codex/cli",
        "refresh_after": "never",
    }
    assert actions[-1]["kind"] == "refresh_readiness"
    assert "Install or expose the Codex CLI" in status["details"]["guidance"]


def test_readiness_status_returns_login_guidance_for_missing_auth(monkeypatch) -> None:  # noqa: ANN001
    status = readiness_from(
        PreflightReport(
            ok=False,
            machine_code=PREFLIGHT_CODE_NOT_AUTHENTICATED,
            reason="login required",
            supported_version_range="0.122.0",
            evidence=RuntimeEvidence(
                runtime_name="codex",
                runtime_version="0.122.0",
                auth_state="unauthenticated",
                entitlement_state="unknown",
                platform="linux/x86_64",
            ),
        ),
        monkeypatch,
    )

    actions = assert_generic_actions(status)
    assert status["label_hint"] == "Login"
    assert actions[0]["id"] == "codex.login.guidance"
    assert actions[0]["kind"] == "show_guidance"
    assert actions[0]["docs_url"] == "https://developers.openai.com/codex/auth"
    assert "complete authentication outside Modly" in actions[0]["guidance"]
    assert status["details"]["diagnostics"]["auth_state"] == "unauthenticated"


def test_readiness_status_returns_access_details_for_missing_entitlement(monkeypatch) -> None:  # noqa: ANN001
    status = readiness_from(
        PreflightReport(
            ok=False,
            machine_code=PREFLIGHT_CODE_NO_ENTITLEMENT,
            reason="unsupported plan",
            supported_version_range="0.122.0",
            evidence=RuntimeEvidence(
                runtime_name="codex",
                runtime_version="0.122.0",
                auth_state="authenticated",
                entitlement_state="free",
                platform="darwin/arm64",
            ),
        ),
        monkeypatch,
    )

    actions = assert_generic_actions(status)
    assert status["label_hint"] == "Login"
    assert actions[0]["id"] == "codex.access.details"
    assert actions[0]["kind"] == "show_details"
    assert actions[1]["docs_url"] == "https://developers.openai.com/codex/pricing"
    assert "Check plan, workspace, or account access" in status["details"]["guidance"]
    assert status["details"]["diagnostics"]["entitlement_state"] == "free"


def test_readiness_status_returns_update_details_without_assuming_root_cause(monkeypatch) -> None:  # noqa: ANN001
    status = readiness_from(
        PreflightReport(
            ok=False,
            machine_code=PREFLIGHT_CODE_UNSUPPORTED_VERSION,
            reason="version is not allowlisted",
            supported_version_range="0.122.0",
            evidence=RuntimeEvidence(
                runtime_name="codex",
                runtime_version="9.9.9",
                runtime_executable="/home/example/.local/bin/codex",
                runtime_version_source="raw command output: CODEX_TOKEN=secret",
                auth_state="authenticated",
                entitlement_state="entitled",
                platform="linux/arm64",
            ),
        ),
        monkeypatch,
    )

    actions = assert_generic_actions(status)
    diagnostics = assert_locked_sanitized_diagnostics(status)
    assert status["label_hint"] == "Update Codex"
    assert actions[0]["id"] == "codex.update.details"
    assert actions[0]["kind"] == "show_details"
    assert actions[1]["label"] == "Update Codex"
    assert "may require changing the local Codex runtime or updating extension compatibility after review" in actions[1]["guidance"]
    assert diagnostics["runtime_version"] == "9.9.9"
    assert diagnostics["supported_versions"] == "0.122.0"
    assert diagnostics["runtime_version_supported"] == "false"


def test_readiness_status_returns_disabled_unsupported_platform_details(monkeypatch) -> None:  # noqa: ANN001
    status = readiness_from(
        PreflightReport(
            ok=False,
            machine_code=PREFLIGHT_CODE_UNSUPPORTED_PLATFORM,
            reason="Platform linux/ppc64le is not enabled for this V1 extension.",
            supported_version_range="0.122.0",
            evidence=RuntimeEvidence(runtime_name="codex", platform="linux/ppc64le"),
        ),
        monkeypatch,
    )

    actions = assert_generic_actions(status)
    assert status["label_hint"] == "Unsupported"
    assert actions[0]["id"] == "codex.unsupported.details"
    assert actions[0]["kind"] == "show_details"
    assert actions[0]["disabled"] is True
    assert "No setup, login, update, or repair action applies" in actions[0]["reason"]
    assert status["details"]["diagnostics"]["platform_supported"] == "false"


def test_readiness_status_returns_ready_details_without_mutation(monkeypatch) -> None:  # noqa: ANN001
    status = readiness_from(
        PreflightReport(
            ok=True,
            supported_version_range="0.122.0",
            evidence=RuntimeEvidence(
                runtime_name="codex",
                runtime_version="0.122.0",
                auth_state="authenticated",
                entitlement_state="entitled",
                platform="linux/x86_64",
            ),
        ),
        monkeypatch,
    )

    actions = assert_generic_actions(status)
    assert status["label_hint"] == "Ready"
    assert actions[0]["id"] == "codex.ready.details"
    assert actions[0]["kind"] == "show_details"
    assert actions[1]["kind"] == "refresh_readiness"
    assert "never starts generation" in status["details"]["summary"]
    assert status["details"]["diagnostics"]["diagnostic_status"] == "ready"


def test_readiness_status_diagnostics_use_only_locked_keys_and_sanitized_values(monkeypatch) -> None:  # noqa: ANN001
    status = readiness_from(
        PreflightReport(
            ok=False,
            machine_code=PREFLIGHT_CODE_NOT_AUTHENTICATED,
            reason="login required",
            supported_version_range="0.122.0",
            evidence=RuntimeEvidence(
                runtime_name="codex",
                runtime_version="0.122.0",
                runtime_executable="/home/example/.local/bin/codex",
                runtime_version_source="raw command output: CODEX_TOKEN=secret",
                auth_state="unauthenticated",
                auth_reason="CODEX_TOKEN=secret from environment",
                entitlement_state="unknown",
                platform="linux/x86_64",
            ),
        ),
        monkeypatch,
    )

    diagnostics = assert_locked_sanitized_diagnostics(status)
    assert diagnostics == {
        "runtime_source": "local-codex-command",
        "runtime_name": "codex",
        "runtime_version": "0.122.0",
        "runtime_version_supported": "true",
        "supported_versions": "0.122.0",
        "platform_supported": "true",
        "platform_key": "linux/x86_64",
        "auth_state": "unauthenticated",
        "entitlement_state": "unknown",
        "extension_setup_state": "ready",
        "extension_import_state": "ready",
        "codex_app_server_state": "not_checked",
        "readiness_source": "codex_extension_preflight",
        "diagnostic_status": "blocked",
        "last_checked_at": status["checked_at"],
    }


def test_generator_adapter_wraps_text_to_image_requests(monkeypatch) -> None:  # noqa: ANN001
    recorded: dict[str, object] = {}

    def fake_generate(payload, *, workspace_root=None, preflight_runner=None, adapter=None):  # noqa: ANN001
        recorded["payload"] = payload
        recorded["workspace_root"] = workspace_root
        return "/tmp/codex-text.png"

    monkeypatch.setattr(generator_module, "generate", fake_generate)

    adapter = generator_module.CodexImageGenerator(Path("/tmp/model"), Path("/tmp/workspace"))
    result = adapter.generate(b"", {"prompt": "draw a fox", "size": "1024x1024"})

    assert result == Path("/tmp/codex-text.png")
    assert recorded["workspace_root"] == Path("/tmp/workspace")
    assert recorded["payload"] == {
        "prompt": "draw a fox",
        "mode": "text-to-image",
        "params": {"prompt": "draw a fox", "size": "1024x1024"},
        "output_target": recorded["payload"]["output_target"],
    }
    assert str(recorded["payload"]["output_target"]).startswith("codex/text-to-image-")


def test_generator_adapter_wraps_image_to_image_requests(monkeypatch) -> None:  # noqa: ANN001
    recorded: dict[str, object] = {}

    def fake_generate(payload, *, workspace_root=None, preflight_runner=None, adapter=None):  # noqa: ANN001
        recorded["payload"] = payload
        recorded["workspace_root"] = workspace_root
        return "/tmp/codex-image.png"

    monkeypatch.setattr(generator_module, "generate", fake_generate)

    adapter = generator_module.CodexImageGenerator(Path("/tmp/model"), Path("/tmp/workspace"))
    result = adapter.generate(b"png-bytes", {"prompt": "edit this", "strength": 0.4, "mode": "image-to-image"})

    assert result == Path("/tmp/codex-image.png")
    assert recorded["workspace_root"] == Path("/tmp/workspace")
    assert recorded["payload"]["mode"] == "image-to-image"
    assert recorded["payload"]["params"] == {
        "prompt": "edit this",
        "strength": 0.4,
        "mode": "image-to-image",
    }
    assert recorded["payload"]["input_image"] == {
        "base64": "cG5nLWJ5dGVz",
        "media_type": "image/png",
    }
    assert str(recorded["payload"]["output_target"]).startswith("codex/image-to-image-")
