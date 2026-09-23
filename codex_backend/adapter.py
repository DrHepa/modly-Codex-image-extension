from __future__ import annotations

import atexit
import base64
import binascii
import importlib
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Callable

from .contracts import (
    IMAGE_TO_IMAGE_MODE,
    PREVIEWABLE_IMAGE_EXTENSIONS,
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
_INSTRUCTION_EXCLUDED_KEYS = frozenset(
    {
        "prompt",
        "input_image_path",
        "reference_image_paths",
        "model",
        "output_target",
        "outputTarget",
        "output_path",
        "outputPath",
        "output",
        "workspace_root",
        "workspaceRoot",
        "cwd",
        "_codex_workspace_root",
        "_codex_cwd",
        "_codex_output_target",
    }
)
_IMAGE_DATA_KEYS = (
    "b64_json",
    "base64",
    "image_base64",
    "imageBase64",
    "image_data",
    "imageData",
    "result",
    "data",
    "content",
)
_MEDIA_TYPE_SUFFIXES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}
_CODEX_WORKSPACE_ROOT_KEY = "_codex_workspace_root"
_CODEX_OUTPUT_TARGET_KEY = "_codex_output_target"
_CODEX_CWD_KEY = "_codex_cwd"
_OFFICIAL_THREAD_ITEM_TYPES = frozenset(
    {
        "agentMessage",
        "commandExecution",
        "imageGeneration",
        "imageView",
        "mcpToolCall",
        "reasoning",
        "userMessage",
    }
)
_OFFICIAL_IMAGE_OUTPUT_ITEM_TYPES = frozenset({"imageGeneration"})

EXTENSION_ROOT = Path(__file__).resolve().parents[1]


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


def _output_thread_items(raw: Any) -> Any:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return raw

    items = list(raw)
    item_types = [str(mapping.get("type")) for item in items if (mapping := _as_mapping(item)).get("type")]
    if not any(item_type in _OFFICIAL_THREAD_ITEM_TYPES for item_type in item_types):
        return items

    return [
        item
        for item in items
        if str(_as_mapping(item).get("type")) in _OFFICIAL_IMAGE_OUTPUT_ITEM_TYPES
    ]


def _extension_site_packages_candidates(extension_root: Path = EXTENSION_ROOT) -> list[Path]:
    venv_dir = extension_root / "venv"
    candidates = [venv_dir / "Lib" / "site-packages"]
    candidates.extend(sorted((venv_dir / "lib").glob("python*/site-packages")))
    return candidates


def _add_extension_venv_site_packages(extension_root: Path = EXTENSION_ROOT) -> None:
    for candidate in _extension_site_packages_candidates(extension_root):
        if not candidate.exists():
            continue
        path_value = str(candidate)
        if path_value not in sys.path:
            sys.path.insert(0, path_value)


def _load_openai_codex() -> Any:
    _add_extension_venv_site_packages(EXTENSION_ROOT)
    try:
        return importlib.import_module("openai_codex")
    except ModuleNotFoundError as exc:
        raise CodexExtensionError(
            RUNTIME_CODE_CALL_FAILED,
            "openai_codex is not importable; run the extension setup to install openai-codex.",
        ) from exc


def _module_runtime_evidence(module: Any) -> dict[str, Any]:
    module_name = getattr(module, "__name__", None) or "openai_codex"
    module_version = getattr(module, "__version__", None)
    return {
        "source": "python-module",
        "runtime_name": module_name,
        "runtime_version": str(module_version) if module_version is not None else None,
    }


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
        if key in _INSTRUCTION_EXCLUDED_KEYS or value is None:
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
        lines.append("Use the first attached local image as the source input.")
    reference_image_paths = payload.get("reference_image_paths")
    reference_count = (
        len(reference_image_paths)
        if isinstance(reference_image_paths, Sequence) and not isinstance(reference_image_paths, (str, bytes, bytearray))
        else 0
    )
    if reference_count:
        lines.append(f"Use the {reference_count} additional attached reference image(s) for visual context.")
    if extra_lines:
        lines.append("Requested generation hints:")
        lines.extend(extra_lines)
    return "\n".join(lines)


def _sdk_thread_inputs(module: Any, mode: str, payload: Mapping[str, Any]) -> list[Any]:
    inputs = [module.TextInput(_build_instruction_text(mode, payload))]
    input_image_path = payload.get("input_image_path")
    if mode == IMAGE_TO_IMAGE_MODE and input_image_path is not None:
        inputs.append(module.LocalImageInput(str(Path(str(input_image_path)).expanduser().resolve())))
    reference_image_paths = payload.get("reference_image_paths")
    if (
        mode == IMAGE_TO_IMAGE_MODE
        and isinstance(reference_image_paths, Sequence)
        and not isinstance(reference_image_paths, (str, bytes, bytearray))
    ):
        for reference_image_path in reference_image_paths:
            inputs.append(module.LocalImageInput(str(Path(str(reference_image_path)).expanduser().resolve())))
    return inputs


def _turn_status_value(turn: Any) -> str | None:
    status = getattr(turn, "status", None)
    if status is None:
        return None
    return getattr(status, "value", str(status))


def _turn_error_message(turn: Any) -> str | None:
    error = getattr(turn, "error", None)
    message = getattr(error, "message", None) if error is not None else None
    if isinstance(message, str) and message.strip():
        return message.strip()
    return None


def _raise_for_failed_turn(turn: Any) -> None:
    if _turn_status_value(turn) != "failed":
        return

    raise CodexExtensionError(
        RUNTIME_CODE_CALL_FAILED,
        _turn_error_message(turn) or "The OpenAI Codex SDK reported a failed turn.",
    )


def _raise_run_failure(exc: Exception) -> None:
    raise CodexExtensionError(
        RUNTIME_CODE_CALL_FAILED,
        str(exc) or "The OpenAI Codex SDK turn failed before returning a result.",
    ) from exc


def _find_turn(turns: Sequence[Any] | None, turn_id: str) -> Any | None:
    for turn in turns or ():
        if getattr(turn, "id", None) == turn_id:
            return turn
    return None


def _resolve_sdk_cwd(payload: Mapping[str, Any]) -> Path:
    raw_cwd = payload.get(_CODEX_CWD_KEY)
    if isinstance(raw_cwd, (str, Path)) and str(raw_cwd).strip():
        try:
            return Path(raw_cwd).expanduser().resolve()
        except (OSError, RuntimeError, ValueError) as exc:
            raise CodexExtensionError(
                RUNTIME_CODE_CALL_FAILED,
                "Invalid Codex working directory for thread_start(cwd=...).",
            ) from exc

    return Path.cwd().resolve()


def _previewable_candidate(path: Path) -> bool:
    try:
        return path.is_file() and path.suffix.lower() in PREVIEWABLE_IMAGE_EXTENSIONS
    except OSError:
        return False


def _codex_output_candidates(cwd: Path) -> set[Path]:
    output_dir = cwd / ".codex-output"
    try:
        if not output_dir.exists() or not output_dir.is_dir():
            return set()
        return {path.resolve() for path in output_dir.rglob("*") if _previewable_candidate(path)}
    except OSError:
        return set()


def _candidate_mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _fallback_candidate_rank(path: Path, output_dir: Path) -> tuple[int, int, int, str]:
    try:
        rel_parts = path.relative_to(output_dir).parts
    except ValueError:
        rel_parts = path.parts
    is_top_level = int(len(rel_parts) == 1)
    name = path.name.lower()
    final_looking = int("imagegen" not in name and "variant" not in name)
    return (is_top_level, final_looking, _candidate_mtime_ns(path), str(path))


def _choose_codex_output_fallback(cwd: Path, before_candidates: set[Path]) -> Path | None:
    output_dir = cwd / ".codex-output"
    new_candidates = _codex_output_candidates(cwd) - before_candidates
    if not new_candidates:
        return None
    return max(new_candidates, key=lambda path: _fallback_candidate_rank(path, output_dir))


def _run_sdk_turn(module: Any, mode: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    cwd = _resolve_sdk_cwd(payload)
    before_candidates = _codex_output_candidates(cwd)
    inputs = _sdk_thread_inputs(module, mode, payload)
    thread_start_kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "sandbox": module.Sandbox.workspace_write,
    }
    model = payload.get("model")
    if isinstance(model, str) and model.strip():
        thread_start_kwargs["model"] = model

    with module.Codex() as codex:
        thread = codex.thread_start(**thread_start_kwargs)
        turn_handle = thread.turn(inputs)
        turn_id = turn_handle.id
        completed_turn = None
        run_failure: Exception | None = None
        try:
            completed_turn = turn_handle.run()
        except Exception as exc:
            # The official SDK raises when a turn finishes as failed. The
            # app-server may still have persisted an image-generation item, so
            # read the thread before deciding that no output can be recovered.
            run_failure = exc
        try:
            persisted = thread.read(include_turns=True)
        except Exception:
            fallback_path = _choose_codex_output_fallback(cwd, before_candidates)
            if fallback_path is not None:
                recovered = {
                    "saved_path": str(fallback_path),
                    "turn_id": turn_id,
                    "turn_status": _turn_status_value(completed_turn),
                    "turn_error": _turn_error_message(completed_turn) or (str(run_failure) if run_failure else None),
                    "codex_output_fallback": True,
                }
                if run_failure is not None:
                    recovered["turn_recovered_after_failure"] = True
                return recovered
            _raise_for_failed_turn(completed_turn)
            if run_failure is not None:
                _raise_run_failure(run_failure)
            raise
        persisted_turn = _find_turn(
            getattr(getattr(persisted, "thread", None), "turns", None),
            turn_id,
        )
        status_turn = persisted_turn or completed_turn
        persisted_items = list(
            getattr(persisted_turn, "items", None) or getattr(completed_turn, "items", None) or [],
        )
        server_info = getattr(codex.metadata, "server_info", None) or getattr(codex.metadata, "serverInfo", None)
        turn_status = _turn_status_value(status_turn)
        turn_error = _turn_error_message(status_turn) or (str(run_failure) if run_failure else None)
        partial_result = {"items": persisted_items}
        explicit_path = _extract_saved_path(partial_result)
        image_data = None if explicit_path else _extract_image_data(partial_result)
        fallback_path = (
            None
            if explicit_path or image_data
            else _choose_codex_output_fallback(cwd, before_candidates)
        )
        has_recoverable_output = (
            explicit_path is not None
            or image_data is not None
            or fallback_path is not None
        )
        recovered_after_failure = bool(
            (turn_status == "failed" or run_failure is not None) and has_recoverable_output
        )
        if not has_recoverable_output:
            _raise_for_failed_turn(status_turn)
            if run_failure is not None:
                _raise_run_failure(run_failure)

        result = {
            "items": persisted_items,
            "turn_id": turn_id,
            "turn_status": turn_status,
            "server_info": {
                "name": getattr(server_info, "name", None),
                "version": getattr(server_info, "version", None),
            },
        }
        if turn_error:
            result["turn_error"] = turn_error
        if fallback_path is not None:
            result["saved_path"] = str(fallback_path)
            result["codex_output_fallback"] = True
        if recovered_after_failure:
            result["turn_recovered_after_failure"] = True
        return result


def _default_invoke(mode: str, payload: Mapping[str, Any]) -> Any:
    module = _load_openai_codex()
    required_exports = ("Codex", "Sandbox", "TextInput", "LocalImageInput")
    missing_exports = [name for name in required_exports if not hasattr(module, name)]
    if missing_exports:
        raise CodexExtensionError(
            RUNTIME_CODE_CALL_FAILED,
            "openai_codex is missing required public exports: " + ", ".join(missing_exports),
        )
    return _run_sdk_turn(module, mode, payload)


def _split_data_image_uri(raw_value: str) -> tuple[str, str] | None:
    stripped = raw_value.strip()
    if not stripped.startswith("data:image/") or ";base64," not in stripped:
        return None

    header, encoded = stripped.split(";base64,", 1)
    media_type = header.removeprefix("data:").split(";", 1)[0].lower()
    return media_type, encoded


def _infer_image_suffix(image_bytes: bytes) -> str | None:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(image_bytes) >= 12 and image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return ".webp"
    return None


def _decode_image_data_string(raw_value: str) -> tuple[bytes, str, str] | None:
    stripped = raw_value.strip()
    if not stripped:
        return None

    data_uri = _split_data_image_uri(stripped)
    media_type = "image"
    encoded = stripped
    suffix: str | None = None
    if data_uri is not None:
        media_type, encoded = data_uri
        suffix = _MEDIA_TYPE_SUFFIXES.get(media_type)

    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return None

    if not image_bytes:
        return None

    inferred_suffix = _infer_image_suffix(image_bytes)
    if suffix is None:
        suffix = inferred_suffix
    if suffix is None:
        return None
    if suffix not in PREVIEWABLE_IMAGE_EXTENSIONS:
        return None

    return image_bytes, suffix, media_type


def _looks_like_image_data(raw_value: str) -> bool:
    return _decode_image_data_string(raw_value) is not None


def _looks_like_path_string(raw_value: str) -> bool:
    stripped = raw_value.strip()
    if not stripped or "\x00" in stripped or "\n" in stripped or "\r" in stripped:
        return False
    if len(stripped) > 4096:
        return False
    if _looks_like_image_data(stripped):
        return False
    if stripped.startswith(("/", "./", "../", "~/")) or "/" in stripped or "\\" in stripped:
        return True
    return Path(stripped).suffix.lower() in PREVIEWABLE_IMAGE_EXTENSIONS


def _write_temp_result_image(image_bytes: bytes, suffix: str) -> Path:
    handle = tempfile.NamedTemporaryFile(prefix="codex-result-", suffix=suffix, delete=False)
    with handle:
        handle.write(image_bytes)

    temp_path = Path(handle.name).resolve()
    atexit.register(lambda: temp_path.exists() and temp_path.unlink())
    return temp_path


def _coerce_saved_path_value(value: Any) -> str | None:
    if isinstance(value, Path):
        return str(value)

    if isinstance(value, str):
        if not value.strip() or _looks_like_image_data(value):
            return None
        return value

    root = getattr(value, "root", None)
    if root is not None and root is not value:
        coerced_root = _coerce_saved_path_value(root)
        if coerced_root:
            return coerced_root

    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        if dumped is not value:
            return _coerce_saved_path_value(dumped)

    return None


def _extract_image_data(raw: Any) -> tuple[bytes, str, str] | None:
    if raw is None:
        return None

    if isinstance(raw, str):
        return _decode_image_data_string(raw)

    if isinstance(raw, Mapping):
        for key in _IMAGE_DATA_KEYS:
            value = raw.get(key)
            decoded = _extract_image_data(value)
            if decoded is not None:
                return decoded

        for key in _NESTED_PATH_KEYS:
            if key in _IMAGE_DATA_KEYS:
                continue
            value = raw.get(key)
            if key == "items":
                value = _output_thread_items(value)
            decoded = _extract_image_data(value)
            if decoded is not None:
                return decoded

    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        for item in raw:
            decoded = _extract_image_data(item)
            if decoded is not None:
                return decoded

    mapping = _as_mapping(raw)
    if mapping and mapping is not raw:
        return _extract_image_data(mapping)

    return None


def _extract_saved_path(raw: Any, *, allow_bare_string: bool = True) -> str | None:
    if raw is None:
        return None

    if isinstance(raw, Path):
        return str(raw)

    if isinstance(raw, str):
        return raw if allow_bare_string and _looks_like_path_string(raw) else None

    if isinstance(raw, Mapping):
        for key in _DIRECT_PATH_KEYS:
            coerced = _coerce_saved_path_value(raw.get(key))
            if coerced:
                return coerced

        for key in _NESTED_PATH_KEYS:
            value = raw.get(key)
            if key == "items":
                value = _output_thread_items(value)
            extracted = _extract_saved_path(value, allow_bare_string=False)
            if extracted:
                return extracted

    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        for item in raw:
            extracted = _extract_saved_path(item, allow_bare_string=allow_bare_string)
            if extracted:
                return extracted

    if hasattr(raw, "saved_path"):
        coerced = _coerce_saved_path_value(getattr(raw, "saved_path"))
        if coerced:
            return coerced

    mapping = _as_mapping(raw)
    if mapping and mapping is not raw:
        return _extract_saved_path(mapping, allow_bare_string=allow_bare_string)

    return None


def _collect_saved_paths(raw: Any, *, allow_bare_string: bool = True) -> list[str]:
    if raw is None:
        return []

    if isinstance(raw, Path):
        return [str(raw)]

    if isinstance(raw, str):
        return [raw] if allow_bare_string and _looks_like_path_string(raw) else []

    if isinstance(raw, Mapping):
        direct_paths: list[str] = []
        for key in _DIRECT_PATH_KEYS:
            coerced = _coerce_saved_path_value(raw.get(key))
            if coerced:
                direct_paths.append(coerced)

        if direct_paths:
            return direct_paths

        nested_paths: list[str] = []
        for key in _NESTED_PATH_KEYS:
            value = raw.get(key)
            if key == "items":
                value = _output_thread_items(value)
            nested_paths.extend(_collect_saved_paths(value, allow_bare_string=False))
        return nested_paths

    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        collected: list[str] = []
        for item in raw:
            collected.extend(_collect_saved_paths(item, allow_bare_string=allow_bare_string))
        return collected

    if hasattr(raw, "saved_path"):
        coerced = _coerce_saved_path_value(getattr(raw, "saved_path"))
        if coerced:
            return [coerced]

    mapping = _as_mapping(raw)
    if mapping and mapping is not raw:
        return _collect_saved_paths(mapping, allow_bare_string=allow_bare_string)

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
        image_data = _extract_image_data(raw)
        if image_data is not None:
            image_bytes, suffix, image_media_type = image_data
            return CodexResult(
                saved_path=_write_temp_result_image(image_bytes, suffix),
                media_type=image_media_type,
                metadata=mapping,
            )

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
            module = _load_openai_codex()
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
        input_image_path: str | Path | None,
        *,
        reference_image_paths: Sequence[str | Path] = (),
        params: Mapping[str, Any] | None = None,
    ) -> CodexResult:
        payload = {
            "prompt": prompt,
        }
        if input_image_path is not None:
            payload["input_image_path"] = str(input_image_path)
        if reference_image_paths:
            payload["reference_image_paths"] = [str(path) for path in reference_image_paths]
        payload.update(dict(params or {}))
        raw = self._invoker(IMAGE_TO_IMAGE_MODE, payload)
        return self._normalize_with_runtime_evidence(raw)

    def generate(self, request: GenerateRequest) -> CodexResult:
        params = dict(request.params)
        params[_CODEX_OUTPUT_TARGET_KEY] = str(request.output_target)
        if request.workspace_root is not None:
            params[_CODEX_WORKSPACE_ROOT_KEY] = str(request.workspace_root)

        if request.mode == IMAGE_TO_IMAGE_MODE:
            return self.image_to_image(
                request.prompt,
                request.input_image_path,
                reference_image_paths=request.reference_image_paths,
                params=params,
            )

        return self.text_to_image(request.prompt, params=params)


__all__ = ["CodexAdapter", "normalize_result"]
