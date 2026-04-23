from __future__ import annotations

from pathlib import Path

import generator as generator_module


def test_generator_class_keeps_node_specific_schema_on_runner_start() -> None:
    assert generator_module.CodexImageGenerator.params_schema() == []


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
