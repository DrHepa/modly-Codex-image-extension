from __future__ import annotations

import sys
from pathlib import Path

import pytest

import codex_backend.adapter as adapter_module
from codex_backend.adapter import CodexAdapter, normalize_result
from codex_backend.contracts import (
    IMAGE_TO_IMAGE_MODE,
    RUNTIME_CODE_CALL_FAILED,
    RUNTIME_CODE_NO_OUTPUT,
    TEXT_TO_IMAGE_MODE,
    GenerateRequest,
)


def test_adapter_maps_prompt_only_requests_to_text_to_image() -> None:
    recorded: list[tuple[str, dict[str, str]]] = []

    def invoker(mode: str, payload: dict[str, str]) -> dict[str, str]:
        recorded.append((mode, payload))
        return {"saved_path": "/tmp/generated.png"}

    adapter = CodexAdapter(invoker=invoker)
    request = GenerateRequest(prompt="draw a fox", output_target=Path("outputs/result.png"), params={"style": "comic"})

    result = adapter.generate(request)

    assert result.saved_path == Path("/tmp/generated.png")
    assert recorded == [(TEXT_TO_IMAGE_MODE, {"prompt": "draw a fox", "style": "comic"})]


def test_adapter_maps_prompt_plus_image_requests_to_image_to_image() -> None:
    recorded: list[tuple[str, dict[str, str]]] = []

    def invoker(mode: str, payload: dict[str, str]) -> dict[str, str]:
        recorded.append((mode, payload))
        return {"saved_path": "/tmp/generated.png"}

    adapter = CodexAdapter(invoker=invoker)
    request = GenerateRequest(
        prompt="edit this",
        output_target=Path("outputs/result.png"),
        input_image_path=Path("/tmp/input.png"),
        params={"strength": 0.4},
    )

    result = adapter.generate(request)

    assert result.saved_path == Path("/tmp/generated.png")
    assert recorded == [
        (
            IMAGE_TO_IMAGE_MODE,
            {
                "prompt": "edit this",
                "input_image_path": "/tmp/input.png",
                "strength": 0.4,
            },
        )
    ]


def test_normalize_result_returns_no_output_code_when_saved_path_is_missing() -> None:
    result = normalize_result({"output": {}, "media_type": "image"})

    assert result.saved_path is None
    assert result.machine_code == RUNTIME_CODE_NO_OUTPUT
    assert result.metadata == {"output": {}, "media_type": "image"}


def test_normalize_result_extracts_saved_path_from_sdk_items_mapping() -> None:
    result = normalize_result(
        {
            "items": [
                {
                    "type": "imageGeneration",
                    "saved_path": "/tmp/generated.png",
                }
            ]
        }
    )

    assert result.saved_path == Path("/tmp/generated.png")
    assert result.machine_code is None


def test_normalize_result_extracts_saved_path_from_sdk_camel_case_mapping() -> None:
    result = normalize_result(
        {
            "items": [
                {
                    "type": "imageGeneration",
                    "savedPath": "/tmp/generated-camel.png",
                }
            ]
        }
    )

    assert result.saved_path == Path("/tmp/generated-camel.png")
    assert result.machine_code is None


def test_default_adapter_reports_missing_public_sdk_exports(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr("codex_backend.adapter._load_codex_app_server", lambda: object())

    with pytest.raises(Exception) as exc_info:
        CodexAdapter().text_to_image("draw a fox")

    assert getattr(exc_info.value, "machine_code", None) == RUNTIME_CODE_CALL_FAILED
    assert "missing required public exports" in str(exc_info.value)


def test_extension_site_packages_candidates_include_windows_venv_path(tmp_path: Path) -> None:
    candidates = adapter_module._extension_site_packages_candidates(tmp_path)

    assert tmp_path / "venv" / "Lib" / "site-packages" in candidates


def test_load_codex_app_server_discovers_extension_venv_site_packages(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    site_packages = tmp_path / "venv" / "Lib" / "site-packages"
    site_packages.mkdir(parents=True)
    (site_packages / "codex_app_server.py").write_text("VALUE = 'from-extension-venv'\n", encoding="utf-8")

    monkeypatch.setattr(adapter_module, "EXTENSION_ROOT", tmp_path)
    monkeypatch.delitem(sys.modules, "codex_app_server", raising=False)
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry != str(site_packages)])

    module = adapter_module._load_codex_app_server()

    assert module.VALUE == "from-extension-venv"
