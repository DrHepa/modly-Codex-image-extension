from __future__ import annotations

from pathlib import Path

import pytest

from codex_backend.contracts import CodexExtensionError, OUTPUT_CODE_INVALID_TARGET, OUTPUT_CODE_UNSUPPORTED_EXTENSION
from codex_backend.persistence import _resolve_destination_path, _validate_workspace_relative_target, persist_result_image, validate_output_target_contract


@pytest.mark.parametrize(
    ("raw_target", "expected_code"),
    [
        ("", OUTPUT_CODE_INVALID_TARGET),
        (".", OUTPUT_CODE_INVALID_TARGET),
        ("../escape.png", OUTPUT_CODE_INVALID_TARGET),
        ("/tmp/escape.png", OUTPUT_CODE_INVALID_TARGET),
    ],
)
def test_validate_workspace_relative_target_rejects_invalid_values(raw_target: str, expected_code: str) -> None:
    with pytest.raises(CodexExtensionError) as exc_info:
        _validate_workspace_relative_target(Path(raw_target))

    assert getattr(exc_info.value, "machine_code", None) == expected_code


def test_resolve_destination_path_creates_filename_for_directory_targets(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    source_path = tmp_path / "source.png"
    source_path.write_bytes(b"png")

    destination = _resolve_destination_path(
        workspace_root,
        Path("outputs"),
        source_path,
        filename_factory=lambda src: f"chosen{src.suffix}",
    )

    assert destination == workspace_root / "outputs" / "chosen.png"


@pytest.mark.parametrize(
    ("raw_target", "expected_code"),
    [("images/final.gif", OUTPUT_CODE_UNSUPPORTED_EXTENSION), ("../escape.png", OUTPUT_CODE_INVALID_TARGET)],
)
def test_validate_output_target_contract_rejects_invalid_targets_before_persistence(
    raw_target: str,
    expected_code: str,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    with pytest.raises(CodexExtensionError) as exc_info:
        validate_output_target_contract(workspace_root, raw_target)

    assert getattr(exc_info.value, "machine_code", None) == expected_code


def test_persist_result_image_returns_previewable_absolute_path_for_file_target(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    source_path = tmp_path / "generated.webp"
    source_path.write_bytes(b"webp")

    resolved = persist_result_image(source_path, workspace_root, "images/final.webp")

    assert resolved.final_abs_path == workspace_root / "images" / "final.webp"
    assert resolved.final_abs_path.is_absolute()
    assert resolved.final_abs_path.exists()
    assert resolved.workspace_rel_path == Path("images/final.webp")
    assert resolved.final_abs_path.read_bytes() == b"webp"


@pytest.mark.parametrize(
    ("source_name", "raw_target"),
    [("generated.png", "images/final.gif"), ("generated.gif", "images/final.png")],
)
def test_persist_result_image_rejects_non_previewable_extensions(
    source_name: str,
    raw_target: str,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    source_path = tmp_path / source_name
    source_path.write_bytes(b"png")

    with pytest.raises(CodexExtensionError) as exc_info:
        persist_result_image(source_path, workspace_root, raw_target)

    assert getattr(exc_info.value, "machine_code", None) == OUTPUT_CODE_UNSUPPORTED_EXTENSION
