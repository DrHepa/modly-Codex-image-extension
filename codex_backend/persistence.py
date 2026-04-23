from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from .contracts import (
    OUTPUT_CODE_INVALID_TARGET,
    OUTPUT_CODE_PERSIST_FAILED,
    OUTPUT_CODE_UNSUPPORTED_EXTENSION,
    PREVIEWABLE_IMAGE_EXTENSIONS,
    CodexExtensionError,
    ResolvedOutput,
)


def _ensure_previewable_extension(path: Path, *, code: str) -> str:
    suffix = path.suffix.lower()
    if suffix not in PREVIEWABLE_IMAGE_EXTENSIONS:
        raise CodexExtensionError(code, f"Unsupported image extension: {path.suffix or '<none>'}")
    return suffix


def _validate_workspace_relative_target(output_target: Path) -> Path:
    raw_target = str(output_target).strip()
    if not raw_target:
        raise CodexExtensionError(OUTPUT_CODE_INVALID_TARGET, "Output target must not be empty.")

    target = Path(raw_target)
    if target.is_absolute():
        raise CodexExtensionError(OUTPUT_CODE_INVALID_TARGET, "Output target must be workspace-relative.")

    if any(part == ".." for part in target.parts):
        raise CodexExtensionError(OUTPUT_CODE_INVALID_TARGET, "Output target must not traverse outside the workspace.")

    if target == Path("."):
        raise CodexExtensionError(OUTPUT_CODE_INVALID_TARGET, "Output target must reference a file or directory.")

    return target


def validate_output_target_contract(workspace_root: str | Path, output_target: str | Path) -> Path:
    workspace_abs = Path(workspace_root).expanduser().resolve()
    target = _validate_workspace_relative_target(Path(output_target))

    if target.suffix:
        _ensure_previewable_extension(target, code=OUTPUT_CODE_UNSUPPORTED_EXTENSION)

    target_abs = (workspace_abs / target).resolve()
    try:
        target_abs.relative_to(workspace_abs)
    except ValueError as exc:
        raise CodexExtensionError(
            OUTPUT_CODE_INVALID_TARGET,
            "Resolved output target escapes the workspace boundary.",
        ) from exc

    return target


def _resolve_destination_path(
    workspace_root: Path,
    output_target: Path,
    source_path: Path,
    *,
    filename_factory: Callable[[Path], str] | None = None,
) -> Path:
    target = validate_output_target_contract(workspace_root, output_target)
    source_extension = _ensure_previewable_extension(source_path, code=OUTPUT_CODE_UNSUPPORTED_EXTENSION)

    workspace_abs = workspace_root.resolve()
    target_abs = (workspace_abs / target).resolve()

    target_is_directory = target_abs.exists() and target_abs.is_dir() or target.suffix == ""
    if target_is_directory:
        factory = filename_factory or (lambda src: f"codex-output{src.suffix.lower()}")
        return target_abs / factory(source_path)

    target_extension = _ensure_previewable_extension(target_abs, code=OUTPUT_CODE_UNSUPPORTED_EXTENSION)
    if target_extension != source_extension:
        return target_abs.with_suffix(target_extension)
    return target_abs


def persist_result_image(
    source_path: str | Path,
    workspace_root: str | Path,
    output_target: str | Path,
    *,
    filename_factory: Callable[[Path], str] | None = None,
) -> ResolvedOutput:
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise CodexExtensionError(OUTPUT_CODE_PERSIST_FAILED, f"Source image does not exist: {source}")

    _ensure_previewable_extension(source, code=OUTPUT_CODE_UNSUPPORTED_EXTENSION)

    workspace_abs = Path(workspace_root).expanduser().resolve()
    destination_abs = _resolve_destination_path(
        workspace_abs,
        Path(output_target),
        source,
        filename_factory=filename_factory,
    )

    destination_abs.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, destination_abs)
    except OSError as exc:
        raise CodexExtensionError(
            OUTPUT_CODE_PERSIST_FAILED,
            f"Failed to persist generated image to {destination_abs}",
        ) from exc

    return ResolvedOutput(
        final_abs_path=destination_abs.resolve(),
        workspace_rel_path=destination_abs.resolve().relative_to(workspace_abs),
        requested_target=Path(output_target),
    )


__all__ = ["persist_result_image", "validate_output_target_contract"]
