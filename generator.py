from __future__ import annotations

import atexit
import base64
import binascii
import json
import os
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from codex_backend.adapter import CodexAdapter
from codex_backend.contracts import (
    REQUEST_CODE_INVALID_INPUT_IMAGE,
    REQUEST_CODE_INVALID_OUTPUT_TARGET,
    REQUEST_CODE_INVALID_PROMPT,
    REQUEST_CODE_MISSING_INPUT_IMAGE,
    RUNTIME_CODE_NO_OUTPUT,
    CodexExtensionError,
    GenerateRequest,
)
from codex_backend.errors import build_error
from codex_backend.persistence import persist_result_image, validate_output_target_contract
from codex_backend.preflight import run_preflight


def _resolve_workspace_root(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()

    env_value = os.environ.get("MODLY_WORKSPACE_ROOT")
    if env_value:
        return Path(env_value).expanduser().resolve()

    return Path.cwd().resolve()


def _pick_first(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _ensure_prompt(raw_prompt: Any) -> str:
    if not isinstance(raw_prompt, str) or not raw_prompt.strip():
        raise build_error(REQUEST_CODE_INVALID_PROMPT)
    return raw_prompt.strip()


def _ensure_output_target(payload: Mapping[str, Any], params: Mapping[str, Any]) -> Path:
    raw_target = _pick_first(
        payload,
        "output_target",
        "outputTarget",
        "output_path",
        "outputPath",
        "output",
    )
    if raw_target is None:
        raw_target = _pick_first(params, "output_target", "output_path", "output")

    if not isinstance(raw_target, str) or not raw_target.strip():
        raise build_error(REQUEST_CODE_INVALID_OUTPUT_TARGET)

    return Path(raw_target.strip())


def _input_suffix_from_payload(payload: Mapping[str, Any]) -> str:
    media_type = str(payload.get("media_type", payload.get("mime_type", "image/png"))).lower()
    if "webp" in media_type:
        return ".webp"
    if "jpeg" in media_type or "jpg" in media_type:
        return ".jpg"
    return ".png"


def _stage_base64_image(raw_value: str, suffix: str) -> Path:
    encoded = raw_value
    if raw_value.startswith("data:") and ";base64," in raw_value:
        encoded = raw_value.split(";base64,", 1)[1]

    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise build_error(
            REQUEST_CODE_INVALID_INPUT_IMAGE,
            detail="Input image payload is not valid base64 data.",
        ) from exc

    handle = tempfile.NamedTemporaryFile(prefix="codex-input-", suffix=suffix, delete=False)
    with handle:
        handle.write(image_bytes)

    temp_path = Path(handle.name).resolve()
    atexit.register(lambda: temp_path.exists() and temp_path.unlink())
    return temp_path


def _stage_input_image(raw_value: Any) -> Path | None:
    if raw_value is None:
        return None

    if isinstance(raw_value, Mapping):
        path_value = _pick_first(raw_value, "path", "input_image_path")
        if isinstance(path_value, str) and path_value.strip():
            return _stage_input_image(path_value)

        data_value = _pick_first(raw_value, "base64", "data", "content")
        if isinstance(data_value, str) and data_value.strip():
            return _stage_base64_image(data_value.strip(), _input_suffix_from_payload(raw_value))

    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if not stripped:
            raise build_error(
                REQUEST_CODE_INVALID_INPUT_IMAGE,
                detail="Input image path is empty.",
            )

        candidate = Path(stripped).expanduser()
        if candidate.exists():
            resolved = candidate.resolve()
            if not resolved.is_file():
                raise build_error(
                    REQUEST_CODE_INVALID_INPUT_IMAGE,
                    detail=f"Input image is not a file: {resolved}",
                )
            return resolved

        return _stage_base64_image(stripped, ".png")

    raise build_error(
        REQUEST_CODE_INVALID_INPUT_IMAGE,
        detail="Input image must be a file path or a base64-capable mapping payload.",
    )


def _ensure_preflight_allowed(report: Any) -> None:
    if report.ok:
        return

    raise build_error(
        report.machine_code or REQUEST_CODE_INVALID_PROMPT,
        detail=report.reason or "Preflight failed.",
        evidence=getattr(report, "evidence", None),
    )


def _ensure_saved_path(result: Any) -> None:
    if result.saved_path is not None:
        return

    raise build_error(
        result.machine_code or RUNTIME_CODE_NO_OUTPUT,
        detail="Codex returned no saved image path.",
    )


def parse_generate_request(payload: Mapping[str, Any]) -> GenerateRequest:
    params = payload.get("params")
    normalized_params = params if isinstance(params, Mapping) else {}
    prompt = _ensure_prompt(_pick_first(payload, "prompt", "text", "input"))
    output_target = _ensure_output_target(payload, normalized_params)
    raw_input_image = _pick_first(
        payload,
        "input_image",
        "inputImage",
        "image",
        "input_image_path",
        "inputImagePath",
    )
    if raw_input_image is None:
        raw_input_image = _pick_first(normalized_params, "input_image", "input_image_path", "image")

    input_image_path = _stage_input_image(raw_input_image)
    requested_mode = _pick_first(payload, "mode") or _pick_first(normalized_params, "mode")
    if requested_mode == "image-to-image" and input_image_path is None:
        raise build_error(REQUEST_CODE_MISSING_INPUT_IMAGE)

    return GenerateRequest(
        prompt=prompt,
        output_target=output_target,
        input_image_path=input_image_path,
        params=dict(normalized_params),
    )


def generate(
    payload: Mapping[str, Any],
    *,
    workspace_root: str | Path | None = None,
    preflight_runner=run_preflight,
    adapter: CodexAdapter | None = None,
) -> str:
    request = parse_generate_request(payload)
    workspace = _resolve_workspace_root(workspace_root)
    validate_output_target_contract(workspace, request.output_target)
    report = preflight_runner()
    _ensure_preflight_allowed(report)

    runtime_adapter = adapter or CodexAdapter()
    result = runtime_adapter.generate(request)
    _ensure_saved_path(result)

    resolved_output = persist_result_image(
        result.saved_path,
        workspace,
        request.output_target,
    )
    return str(resolved_output.final_abs_path)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, Mapping):
            raise build_error(REQUEST_CODE_INVALID_PROMPT, detail="Generator input must be a JSON object.")
        output_path = generate(payload)
    except CodexExtensionError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
