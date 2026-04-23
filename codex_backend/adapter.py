from __future__ import annotations

import importlib
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


def _candidate_paths(mode: str) -> Sequence[tuple[str, ...]]:
    if mode == TEXT_TO_IMAGE_MODE:
        return (
            ("generate_text_to_image",),
            ("text_to_image",),
            ("generate_image",),
            ("client", "generate_text_to_image"),
            ("client", "text_to_image"),
            ("client", "generate_image"),
        )

    return (
        ("generate_image_to_image",),
        ("image_to_image",),
        ("edit_image",),
        ("client", "generate_image_to_image"),
        ("client", "image_to_image"),
        ("client", "edit_image"),
    )


def _resolve_attr(root: Any, path: Sequence[str]) -> Any:
    current = root
    for segment in path:
        if not hasattr(current, segment):
            return None
        current = getattr(current, segment)
    return current


def _coerce_callable(candidate: Any) -> Callable[..., Any] | None:
    if isinstance(candidate, type):
        try:
            candidate = candidate()
        except TypeError:
            return None

    if callable(candidate):
        return candidate

    return None


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


def _call_candidate(candidate: Callable[..., Any], payload: Mapping[str, Any]) -> Any:
    try:
        return candidate(**payload)
    except TypeError:
        prompt = payload.get("prompt")
        input_image_path = payload.get("input_image_path")
        extra = {key: value for key, value in payload.items() if key not in {"prompt", "input_image_path"}}
        if input_image_path is None:
            return candidate(prompt, **extra)
        return candidate(prompt, input_image_path, **extra)


def _default_invoke(mode: str, payload: Mapping[str, Any]) -> Any:
    module = _load_codex_app_server()
    for candidate_path in _candidate_paths(mode):
        resolved = _resolve_attr(module, candidate_path)
        callable_candidate = _coerce_callable(resolved)
        if callable_candidate is None:
            continue
        return _call_candidate(callable_candidate, payload)

    raise CodexExtensionError(
        RUNTIME_CODE_CALL_FAILED,
        f"codex_app_server does not expose a supported {mode} entrypoint.",
    )


def _extract_saved_path(raw: Any) -> str | None:
    if raw is None:
        return None

    if isinstance(raw, (str, Path)):
        return str(raw)

    if isinstance(raw, Mapping):
        for key in ("saved_path", "image_path", "file_path", "output_path", "path", "local_path"):
            value = raw.get(key)
            if isinstance(value, (str, Path)) and str(value).strip():
                return str(value)

        for key in ("result", "image", "output", "outputs", "images", "artifacts", "data"):
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
        for key in ("saved_path", "image_path", "file_path", "output_path", "path", "local_path"):
            value = raw.get(key)
            if isinstance(value, (str, Path)) and str(value).strip():
                direct_paths.append(str(value))

        if direct_paths:
            return direct_paths

        nested_paths: list[str] = []
        for key in ("result", "image", "output", "outputs", "images", "artifacts", "data"):
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
