from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

from codex_backend.adapter import CodexAdapter
from codex_backend.contracts import GenerateRequest, PreflightReport, RuntimeEvidence

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "manifest.json"


def fake_generate_text_to_image(prompt: str, **_: object) -> dict[str, str]:
    return {"saved_path": "/tmp/runtime-output.png", "provider": prompt}


FakeCodexModule = SimpleNamespace(
    __name__="codex_app_server",
    __version__="0.9.0",
    generate_text_to_image=fake_generate_text_to_image,
)


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_runtime_evidence_stays_outside_planned_manifest_identity(monkeypatch) -> None:  # noqa: ANN001
    original_manifest = load_manifest()
    monkeypatch.setattr("codex_backend.adapter._load_codex_app_server", lambda: FakeCodexModule)

    adapter = CodexAdapter()
    result = adapter.generate(
        GenerateRequest(
            prompt="draw a fox",
            output_target=Path("images/final.png"),
        )
    )
    report = PreflightReport(
        ok=True,
        evidence=RuntimeEvidence(runtime_name="codex", runtime_version="1.2.3", auth_state="authenticated"),
    )

    assert result.metadata["runtime_evidence"] == {
        "source": "python-module",
        "runtime_name": "codex_app_server",
        "runtime_version": "0.9.0",
    }
    assert report.evidence.runtime_name == "codex"
    assert load_manifest() == original_manifest
    assert [node["id"] for node in original_manifest["nodes"]] == ["text-to-image", "image-to-image"]
    assert "runtime_evidence" not in original_manifest
    assert all("runtime_evidence" not in node for node in original_manifest["nodes"])
