from __future__ import annotations

from pathlib import Path

import generator as generator_module
from codex_backend.contracts import (
    IMAGE_TO_IMAGE_MODE,
    PREFLIGHT_CODE_CODEX_MISSING,
    PREFLIGHT_CODE_NOT_AUTHENTICATED,
    PREFLIGHT_CODE_NO_ENTITLEMENT,
    PREFLIGHT_CODE_UNSUPPORTED_PLATFORM,
    PREFLIGHT_CODE_UNSUPPORTED_VERSION,
    PreflightReport,
    RuntimeEvidence,
)


GENERIC_ACTION_KINDS = {"open_external_url", "refresh_readiness"}


def readiness_from(report: PreflightReport, monkeypatch) -> dict[str, object]:  # noqa: ANN001
    monkeypatch.setattr(generator_module, "run_preflight", lambda: report)
    adapter = generator_module.CodexImageGenerator(Path("/tmp/model"), Path("/tmp/workspace"))
    return adapter.readiness_status()


def assert_generic_actions(status: dict[str, object]) -> list[dict[str, object]]:
    actions = status["actions"]
    assert isinstance(actions, list)
    assert len(actions) <= 5
    for action in actions:
        assert action["kind"] in GENERIC_ACTION_KINDS
        assert action["safety"] in {"manual", "non_destructive", "confirm"}
        assert "repair_extension" != action["kind"]
    return actions


def assert_no_verbose_readiness_details(status: dict[str, object]) -> None:
    assert status.get("details", {}) == {}
    serialized = repr(status)
    assert "/home/example" not in serialized
    assert r"C:\Users\example" not in serialized
    assert "CODEX_TOKEN" not in serialized
    assert "secret" not in serialized
    assert "raw command output" not in serialized


def test_generator_class_keeps_node_specific_schema_on_runner_start() -> None:
    assert generator_module.CodexImageGenerator.params_schema() == []


def test_reference_only_request_resolves_image_to_image_mode(tmp_path: Path) -> None:
    reference_path = tmp_path / "reference.png"
    reference_path.write_bytes(b"ref")

    request = generator_module.parse_generate_request(
        {
            "prompt": "use this reference",
            "mode": IMAGE_TO_IMAGE_MODE,
            "output_target": "images/final.png",
            "referenceImagePaths": str(reference_path),
        }
    )

    assert request.mode == IMAGE_TO_IMAGE_MODE
    assert request.input_image_path is None
    assert request.reference_image_paths == (reference_path.resolve(),)


def test_side_image_params_stage_as_references_after_explicit_refs(tmp_path: Path) -> None:
    explicit_path = tmp_path / "explicit.png"
    left_path = tmp_path / "left.png"
    back_path = tmp_path / "back.png"
    right_path = tmp_path / "right.png"
    for path in (explicit_path, left_path, back_path, right_path):
        path.write_bytes(path.stem.encode("utf-8"))

    request = generator_module.parse_generate_request(
        {
            "prompt": "combine side views",
            "mode": IMAGE_TO_IMAGE_MODE,
            "output_target": "images/final.png",
            "params": {
                "reference_images": str(explicit_path),
                "left_image_path": str(left_path),
                "back_image_path": str(back_path),
                "right_image_path": str(right_path),
                "strength": 0.5,
            },
        }
    )

    assert request.reference_image_paths == (
        explicit_path.resolve(),
        left_path.resolve(),
        back_path.resolve(),
        right_path.resolve(),
    )
    assert request.params == {"strength": 0.5}


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
    assert adapter.readiness_status()["label_hint"] == "Update Extension"
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
        "id": "codex.setup.docs",
        "kind": "open_external_url",
        "label": "Open Codex setup docs",
        "safety": "manual",
        "docs_url": "https://developers.openai.com/codex/cli",
        "refresh_after": "never",
    }
    assert actions[-1]["kind"] == "refresh_readiness"
    assert_no_verbose_readiness_details(status)


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
    assert actions[0]["id"] == "codex.login.docs"
    assert actions[0]["kind"] == "open_external_url"
    assert actions[0]["docs_url"] == "https://developers.openai.com/codex/auth"
    assert_no_verbose_readiness_details(status)


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
    assert actions[0]["id"] == "codex.access.docs"
    assert actions[0]["kind"] == "open_external_url"
    assert actions[0]["docs_url"] == "https://developers.openai.com/codex/pricing"
    assert_no_verbose_readiness_details(status)


def test_readiness_status_returns_extension_compatibility_guidance_without_codex_update_claim(monkeypatch) -> None:  # noqa: ANN001
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
    assert status["label_hint"] == "Update Extension"
    assert status["label_hint"] != "Update Codex"
    assert actions[0]["id"] == "extension.compatibility.docs"
    assert actions[0]["kind"] == "open_external_url"
    assert actions[0]["label"] == "Open extension changelog"
    assert actions[0]["label"] != "Open Codex changelog"
    assert "modly-Codex-image-extension" in actions[0]["docs_url"]
    assert "developers.openai.com/codex/changelog" not in actions[0]["docs_url"]
    assert status["evidence"]["runtime_version"] == "9.9.9"
    assert_no_verbose_readiness_details(status)


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
    assert actions == []
    assert_no_verbose_readiness_details(status)


def test_readiness_status_reports_windows_x86_64_as_experimental_and_sanitized(monkeypatch) -> None:  # noqa: ANN001
    status = readiness_from(
        PreflightReport(
            ok=True,
            supported_version_range="0.122.0, 0.124.0",
            evidence=RuntimeEvidence(
                runtime_name="codex",
                runtime_version="0.124.0",
                runtime_executable=r"C:\Users\example\AppData\Local\codex.cmd",
                runtime_version_source="raw command output: CODEX_TOKEN=secret",
                auth_state="authenticated",
                auth_reason="CODEX_TOKEN=secret from environment",
                entitlement_state="entitled",
                platform="windows/x86_64",
            ),
        ),
        monkeypatch,
    )

    assert status["evidence"]["platform"] == "windows/x86_64"
    assert_no_verbose_readiness_details(status)


def test_readiness_status_keeps_windows_arm64_unsupported(monkeypatch) -> None:  # noqa: ANN001
    status = readiness_from(
        PreflightReport(
            ok=False,
            machine_code=PREFLIGHT_CODE_UNSUPPORTED_PLATFORM,
            reason="Platform windows/arm64 is not enabled for this V1 extension.",
            supported_version_range="0.122.0, 0.124.0",
            evidence=RuntimeEvidence(runtime_name="codex", platform="windows/arm64"),
        ),
        monkeypatch,
    )

    assert status["label_hint"] == "Unsupported"
    assert status["evidence"]["platform"] == "windows/arm64"
    assert_no_verbose_readiness_details(status)


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
    assert actions[0]["kind"] == "refresh_readiness"
    assert_no_verbose_readiness_details(status)


def test_readiness_status_omits_verbose_debug_details_and_sanitizes_values(monkeypatch) -> None:  # noqa: ANN001
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

    assert_no_verbose_readiness_details(status)
    assert status["evidence"] == {
        "source": "local-codex-command",
        "runtime_name": "codex",
        "runtime_version": "0.122.0",
        "auth_state": "unauthenticated",
        "entitlement_state": "unknown",
        "platform": "linux/x86_64",
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
