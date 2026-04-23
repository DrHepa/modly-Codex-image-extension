from __future__ import annotations

import importlib
import os
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Callable

from .contracts import (
    IMAGE_TO_IMAGE_MODE,
    RUNTIME_CODE_CALL_FAILED,
    RUNTIME_CODE_MULTI_OUTPUT,
    RUNTIME_CODE_NO_OUTPUT,
    TEXT_TO_IMAGE_MODE,
    CodexExtensionError,
    CodexResult,
    GenerateRequest,
)

ResultInvoker = Callable[[str, Mapping[str, Any]], Any]

_DIRECT_PATH_KEYS = (
    "saved_path",
    "savedPath",
    "image_path",
    "imagePath",
    "file_path",
    "filePath",
    "output_path",
    "outputPath",
    "path",
    "local_path",
    "localPath",
)
_NESTED_PATH_KEYS = (
    "result",
    "image",
    "output",
    "outputs",
    "images",
    "artifacts",
    "data",
    "items",
    "turn",
)


def _as_mapping(raw: Any) -> Mapping[str, Any]:
    if isinstance(raw, Mapping):
        return raw

    if hasattr(raw, "model_dump"):
        dumped = raw.model_dump()
        if isinstance(dumped, Mapping):
            return dumped

    if hasattr(raw, "dict"):
        dumped = raw.dict()
        if isinstance(dumped, Mapping):
            return dumped

    if hasattr(raw, "__dict__"):
        values = vars(raw)
        if isinstance(values, Mapping):
            return values

    return {}


def _load_codex_app_server() -> Any:
    try:
        return importlib.import_module("codex_app_server")
    except ModuleNotFoundError as exc:
        raise CodexExtensionError(
            RUNTIME_CODE_CALL_FAILED,
            "codex_app_server is not importable; install or vendor it before running this extension.",
        ) from exc


def _module_runtime_evidence(module: Any) -> dict[str, Any]:
    module_name = getattr(module, "__name__", None) or "codex_app_server"
    module_version = getattr(module, "__version__", None)
    return {
        "source": "python-module",
        "runtime_name": module_name,
        "runtime_version": str(module_version) if module_version is not None else None,
    }


def _resolve_codex_bin(payload: Mapping[str, Any]) -> str:
    explicit = payload.get("codex_bin")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    env_value = os.environ.get("CODEX_BIN")
    if isinstance(env_value, str) and env_value.strip():
        return env_value.strip()

    resolved = shutil.which("codex")
    if resolved:
        return resolved

    raise CodexExtensionError(
        RUNTIME_CODE_CALL_FAILED,
        "Unable to resolve the local codex binary for AppServerConfig.codex_bin.",
    )


def _stringify_param_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _build_instruction_text(mode: str, payload: Mapping[str, Any]) -> str:
    prompt = str(payload.get("prompt", "")).strip()
    extra_lines = []
    for key, value in payload.items():
        if key in {"prompt", "input_image_path", "codex_bin"} or value is None:
            continue
        extra_lines.append(f"- {key}: {_stringify_param_value(value)}")

    lines = [
        (
            "Create exactly one new image."
            if mode == TEXT_TO_IMAGE_MODE
            else "Edit the provided local image into exactly one output image."
        ),
        "Save the final image to a local file so the app-server returns a saved path.",
        "Do not create multiple variants.",
        f"Prompt: {prompt}",
    ]
    if payload.get("input_image_path") is not None:
        lines.append("Use the attached local reference image as the source input.")
    if extra_lines:
        lines.append("Requested generation hints:")
        lines.extend(extra_lines)
    return "\n".join(lines)


def _sdk_thread_inputs(module: Any, mode: str, payload: Mapping[str, Any]) -> list[Any]:
    inputs = [module.TextInput(_build_instruction_text(mode, payload))]
    input_image_path = payload.get("input_image_path")
    if mode == IMAGE_TO_IMAGE_MODE and input_image_path is not None:
        inputs.append(module.LocalImageInput(str(Path(str(input_image_path)).expanduser().resolve())))
    return inputs


def _turn_status_value(turn: Any) -> str | None:
    status = getattr(turn, "status", None)
    if status is None:
        return None
    return getattr(status, "value", str(status))


def _raise_for_failed_turn(turn: Any) -> None:
    if _turn_status_value(turn) != "failed":
        return

    error = getattr(turn, "error", None)
    message = getattr(error, "message", None) if error is not None else None
    raise CodexExtensionError(
        RUNTIME_CODE_CALL_FAILED,
        (message or "codex_app_server reported a failed turn.").strip(),
    )


def _find_turn(turns: Sequence[Any] | None, turn_id: str) -> Any | None:
    for turn in turns or ():
        if getattr(turn, "id", None) == turn_id:
            return turn
    return None


def _run_sdk_turn(module: Any, mode: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    config = module.AppServerConfig(codex_bin=_resolve_codex_bin(payload), cwd=os.getcwd())
    inputs = _sdk_thread_inputs(module, mode, payload)

    with module.Codex(config=config) as codex:
        thread = codex.thread_start()
        turn_handle = thread.turn(inputs)
        completed_turn = turn_handle.run()
        _raise_for_failed_turn(completed_turn)
        persisted = thread.read(include_turns=True)
        persisted_turn = _find_turn(getattr(getattr(persisted, "thread", None), "turns", None), turn_handle.id)
        persisted_items = list(getattr(persisted_turn, "items", None) or [])
        server_info = getattr(codex.metadata, "serverInfo", None)
        return {
            "items": persisted_items,
            "turn_id": turn_handle.id,
            "turn_status": _turn_status_value(completed_turn),
            "server_info": {
                "name": getattr(server_info, "name", None),
                "version": getattr(server_info, "version", None),
            },
        }


def _default_invoke(mode: str, payload: Mapping[str, Any]) -> Any:
    module = _load_codex_app_server()
    required_exports = ("Codex", "AppServerConfig", "TextInput", "LocalImageInput")
    missing_exports = [name for name in required_exports if not hasattr(module, name)]
    if missing_exports:
        raise CodexExtensionError(
            RUNTIME_CODE_CALL_FAILED,
            "codex_app_server is missing required public exports: " + ", ".join(missing_exports),
        )
    return _run_sdk_turn(module, mode, payload)


def _extract_saved_path(raw: Any) -> str | None:
    if raw is None:
        return None

    if isinstance(raw, (str, Path)):
        return str(raw)

    if isinstance(raw, Mapping):
        for key in _DIRECT_PATH_KEYS:
            value = raw.get(key)
            if isinstance(value, (str, Path)) and str(value).strip():
                return str(value)

        for key in _NESTED_PATH_KEYS:
            value = raw.get(key)
            extracted = _extract_saved_path(value)
            if extracted:
                return extracted

    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        for item in raw:
            extracted = _extract_saved_path(item)
            if extracted:
                return extracted

    if hasattr(raw, "saved_path"):
        value = getattr(raw, "saved_path")
        if value:
            return str(value)

    mapping = _as_mapping(raw)
    if mapping and mapping is not raw:
        return _extract_saved_path(mapping)

    return None


def _collect_saved_paths(raw: Any) -> list[str]:
    if raw is None:
        return []

    if isinstance(raw, (str, Path)):
        return [str(raw)] if str(raw).strip() else []

    if isinstance(raw, Mapping):
        direct_paths: list[str] = []
        for key in _DIRECT_PATH_KEYS:
            value = raw.get(key)
            if isinstance(value, (str, Path)) and str(value).strip():
                direct_paths.append(str(value))

        if direct_paths:
            return direct_paths

        nested_paths: list[str] = []
        for key in _NESTED_PATH_KEYS:
            nested_paths.extend(_collect_saved_paths(raw.get(key)))
        return nested_paths

    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        collected: list[str] = []
        for item in raw:
            collected.extend(_collect_saved_paths(item))
        return collected

    if hasattr(raw, "saved_path"):
        value = getattr(raw, "saved_path")
        if value:
            return [str(value)]

    mapping = _as_mapping(raw)
    if mapping and mapping is not raw:
        return _collect_saved_paths(mapping)

    return []


def normalize_result(raw: Any) -> CodexResult:
    if isinstance(raw, CodexResult):
        return raw

    mapping = _as_mapping(raw)
    media_type = str(mapping.get("media_type", mapping.get("type", "image"))) if mapping else "image"
    saved_paths = [path for path in _collect_saved_paths(raw) if path]
    unique_saved_paths = list(dict.fromkeys(saved_paths))
    if len(unique_saved_paths) > 1:
        return CodexResult(
            saved_path=None,
            media_type=media_type,
            metadata=mapping,
            machine_code=RUNTIME_CODE_MULTI_OUTPUT,
        )

    saved_path = _extract_saved_path(raw)
    if not saved_path:
        return CodexResult(
            saved_path=None,
            media_type=media_type,
            metadata=mapping,
            machine_code=RUNTIME_CODE_NO_OUTPUT,
        )

    return CodexResult(
        saved_path=Path(saved_path),
        media_type=media_type,
        metadata=mapping,
    )


class CodexAdapter:
    def __init__(self, *, invoker: ResultInvoker | None = None) -> None:
        self._invoker = invoker or _default_invoke
        self._uses_default_invoker = invoker is None

    def _runtime_evidence(self) -> dict[str, Any]:
        if not self._uses_default_invoker:
            return {}

        try:
            module = _load_codex_app_server()
        except CodexExtensionError:
            return {}

        return _module_runtime_evidence(module)

    def _normalize_with_runtime_evidence(self, raw: Any) -> CodexResult:
        normalized = normalize_result(raw)
        metadata = dict(normalized.metadata)
        evidence = self._runtime_evidence()
        if evidence:
            metadata["runtime_evidence"] = {key: value for key, value in evidence.items() if value is not None}

        return CodexResult(
            saved_path=normalized.saved_path,
            media_type=normalized.media_type,
            metadata=metadata,
            machine_code=normalized.machine_code,
        )

    def text_to_image(self, prompt: str, *, params: Mapping[str, Any] | None = None) -> CodexResult:
        payload = {"prompt": prompt, **dict(params or {})}
        raw = self._invoker(TEXT_TO_IMAGE_MODE, payload)
        return self._normalize_with_runtime_evidence(raw)

    def image_to_image(
        self,
        prompt: str,
        input_image_path: str | Path,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> CodexResult:
        payload = {
            "prompt": prompt,
            "input_image_path": str(input_image_path),
            **dict(params or {}),
        }
        raw = self._invoker(IMAGE_TO_IMAGE_MODE, payload)
        return self._normalize_with_runtime_evidence(raw)

    def generate(self, request: GenerateRequest) -> CodexResult:
        if request.mode == IMAGE_TO_IMAGE_MODE and request.input_image_path is not None:
            return self.image_to_image(
                request.prompt,
                request.input_image_path,
                params=request.params,
            )

        return self.text_to_image(request.prompt, params=request.params)


__all__ = ["CodexAdapter", "normalize_result"]
