from __future__ import annotations

from pathlib import Path

import pytest

from codex_backend.adapter import CodexAdapter
from codex_backend.contracts import (
    OUTPUT_CODE_INVALID_TARGET,
    OUTPUT_CODE_UNSUPPORTED_EXTENSION,
    PREFLIGHT_CODE_NOT_AUTHENTICATED,
    RUNTIME_CODE_MULTI_OUTPUT,
    RUNTIME_CODE_NO_OUTPUT,
    CodexResult,
    PreflightReport,
    RuntimeEvidence,
)
from generator import generate


class FakeAdapter:
    def __init__(self, result: CodexResult) -> None:
        self._result = result
        self.calls = 0

    def generate(self, request):  # noqa: ANN001 - seam mirrors production adapter
        self.calls += 1
        return self._result


class RecordingAdapter(FakeAdapter):
    def __init__(self, result: CodexResult) -> None:
        super().__init__(result)
        self.requests = []

    def generate(self, request):  # noqa: ANN001 - seam mirrors production adapter
        self.requests.append(request)
        return super().generate(request)


def passing_preflight() -> PreflightReport:
    return PreflightReport(ok=True, evidence=RuntimeEvidence(runtime_name="codex", runtime_version="1.2.3"))


class PreflightRecorder:
    def __init__(self, report: PreflightReport | None = None) -> None:
        self.calls = 0
        self._report = report or passing_preflight()

    def __call__(self) -> PreflightReport:
        self.calls += 1
        return self._report


def test_generate_returns_persisted_absolute_path_on_success(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    source_path = tmp_path / "source.png"
    source_path.write_bytes(b"png")
    adapter = FakeAdapter(CodexResult(saved_path=source_path))

    output_path = generate(
        {"prompt": "draw a fox", "output_target": "images/final.png"},
        workspace_root=workspace_root,
        preflight_runner=passing_preflight,
        adapter=adapter,
    )

    assert output_path == str(workspace_root / "images" / "final.png")
    assert Path(output_path).read_bytes() == b"png"
    assert adapter.calls == 1


def test_generate_prompt_plus_image_returns_persisted_absolute_path(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    source_path = tmp_path / "source.png"
    source_path.write_bytes(b"png")
    adapter = RecordingAdapter(CodexResult(saved_path=source_path))

    output_path = generate(
        {
            "prompt": "edit this sketch",
            "output_target": "images/final.png",
            "input_image": {"base64": "cG5n", "media_type": "image/png"},
        },
        workspace_root=workspace_root,
        preflight_runner=passing_preflight,
        adapter=adapter,
    )

    assert output_path == str(workspace_root / "images" / "final.png")
    assert Path(output_path).read_bytes() == b"png"
    assert adapter.calls == 1
    assert len(adapter.requests) == 1
    request = adapter.requests[0]
    assert request.mode == "image-to-image"
    assert request.input_image_path is not None
    assert request.input_image_path.exists()
    assert request.input_image_path.read_bytes() == b"png"


def test_generate_stages_reference_images_and_sanitizes_raw_image_params(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    runtime_output = tmp_path / "source.png"
    runtime_output.write_bytes(b"png")
    reference_path = tmp_path / "reference.png"
    reference_path.write_bytes(b"ref-path")
    adapter = RecordingAdapter(CodexResult(saved_path=runtime_output))

    output_path = generate(
        {
            "prompt": "edit with references",
            "output_target": "images/final.png",
            "input_image": {"base64": "cHJpbWFyeQ==", "media_type": "image/png"},
            "params": {
                "strength": 0.5,
                "reference_images": [
                    str(reference_path),
                    {"data": "data:image/png;base64,cmVmLWRhdGE=", "media_type": "image/png"},
                ],
            },
        },
        workspace_root=workspace_root,
        preflight_runner=passing_preflight,
        adapter=adapter,
    )

    assert output_path == str(workspace_root / "images" / "final.png")
    request = adapter.requests[0]
    assert request.mode == "image-to-image"
    assert request.input_image_path is not None
    assert request.input_image_path.read_bytes() == b"primary"
    assert len(request.reference_image_paths) == 2
    assert request.reference_image_paths[0] == reference_path.resolve()
    assert request.reference_image_paths[1].exists()
    assert request.reference_image_paths[1].read_bytes() == b"ref-data"
    assert request.params == {"strength": 0.5}


def test_generate_fails_fast_when_preflight_is_blocked(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    adapter = FakeAdapter(CodexResult(saved_path=tmp_path / "unused.png"))

    def blocked_preflight() -> PreflightReport:
        return PreflightReport(
            ok=False,
            machine_code=PREFLIGHT_CODE_NOT_AUTHENTICATED,
            reason="login required",
            evidence=RuntimeEvidence(runtime_name="codex", auth_state="unauthenticated"),
        )

    with pytest.raises(Exception) as exc_info:
        generate(
            {"prompt": "draw a fox", "output_target": "images/final.png"},
            workspace_root=workspace_root,
            preflight_runner=blocked_preflight,
            adapter=adapter,
        )

    assert getattr(exc_info.value, "machine_code", None) == PREFLIGHT_CODE_NOT_AUTHENTICATED
    assert adapter.calls == 0


@pytest.mark.parametrize(
    ("output_target", "expected_code"),
    [
        ("../escape.png", OUTPUT_CODE_INVALID_TARGET),
        ("/tmp/escape.png", OUTPUT_CODE_INVALID_TARGET),
        ("images/final.gif", OUTPUT_CODE_UNSUPPORTED_EXTENSION),
    ],
)
def test_generate_rejects_invalid_output_target_before_runtime_execution(
    output_target: str,
    expected_code: str,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    source_path = tmp_path / "source.png"
    source_path.write_bytes(b"png")
    adapter = FakeAdapter(CodexResult(saved_path=source_path))
    preflight = PreflightRecorder()

    with pytest.raises(Exception) as exc_info:
        generate(
            {"prompt": "draw a fox", "output_target": output_target},
            workspace_root=workspace_root,
            preflight_runner=preflight,
            adapter=adapter,
        )

    assert getattr(exc_info.value, "machine_code", None) == expected_code
    assert preflight.calls == 0
    assert adapter.calls == 0


def test_generate_fails_when_codex_returns_no_saved_output(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    adapter = FakeAdapter(CodexResult(saved_path=None, machine_code=RUNTIME_CODE_NO_OUTPUT))

    with pytest.raises(Exception) as exc_info:
        generate(
            {"prompt": "draw a fox", "output_target": "images/final.png"},
            workspace_root=workspace_root,
            preflight_runner=passing_preflight,
            adapter=adapter,
        )

    assert getattr(exc_info.value, "machine_code", None) == RUNTIME_CODE_NO_OUTPUT
    assert adapter.calls == 1


def test_generate_rejects_multi_output_results_as_out_of_scope(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    adapter = CodexAdapter(
        invoker=lambda mode, payload: {
            "images": [
                {"saved_path": str(first)},
                {"saved_path": str(second)},
            ]
        }
    )

    with pytest.raises(Exception) as exc_info:
        generate(
            {"prompt": "draw variants", "output_target": "images/final.png"},
            workspace_root=workspace_root,
            preflight_runner=passing_preflight,
            adapter=adapter,
        )

    assert getattr(exc_info.value, "machine_code", None) == RUNTIME_CODE_MULTI_OUTPUT
