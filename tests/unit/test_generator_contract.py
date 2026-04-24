from __future__ import annotations

from pathlib import Path

import generator as generator_module
from codex_backend.contracts import (
    PREFLIGHT_CODE_CODEX_MISSING,
    PREFLIGHT_CODE_NOT_AUTHENTICATED,
    PREFLIGHT_CODE_UNSUPPORTED_VERSION,
    PreflightReport,
    RuntimeEvidence,
)


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
