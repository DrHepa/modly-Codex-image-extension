from __future__ import annotations

import atexit
import base64
import binascii
import json
import os
import sys
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codex_backend.adapter import CodexAdapter
from codex_backend.contracts import (
    GENERATOR_CLASS,
    IMAGE_TO_IMAGE_MODE,
    PREFLIGHT_CODE_CODEX_MISSING,
    PREFLIGHT_CODE_NOT_AUTHENTICATED,
    PREFLIGHT_CODE_NO_ENTITLEMENT,
    PREFLIGHT_CODE_UNSUPPORTED_PLATFORM,
    PREFLIGHT_CODE_UNSUPPORTED_VERSION,
    REQUEST_CODE_INVALID_INPUT_IMAGE,
    REQUEST_CODE_INVALID_OUTPUT_TARGET,
    REQUEST_CODE_INVALID_PROMPT,
    REQUEST_CODE_MISSING_INPUT_IMAGE,
    RUNTIME_CODE_NO_OUTPUT,
    TEXT_TO_IMAGE_MODE,
    CodexExtensionError,
    GenerateRequest,
)
from codex_backend.errors import build_error
from codex_backend.persistence import persist_result_image, validate_output_target_contract
from codex_backend.preflight import run_preflight


CODEX_SETUP_DOCS_URL = "https://developers.openai.com/codex/cli"
CODEX_AUTH_DOCS_URL = "https://developers.openai.com/codex/auth"
CODEX_ACCESS_DOCS_URL = "https://developers.openai.com/codex/pricing"
EXTENSION_CHANGELOG_URL = "https://github.com/DrHepa/modly-Codex-image-extension/blob/main/CHANGELOG.md"

REFERENCE_IMAGE_KEYS = (
    "input_images",
    "inputImages",
    "reference_images",
    "referenceImages",
    "reference_image_paths",
    "referenceImagePaths",
)
SIDE_REFERENCE_IMAGE_KEYS = (
    "left_image_path",
    "back_image_path",
    "right_image_path",
)


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


def _pick_reference_images(primary: Mapping[str, Any], fallback: Mapping[str, Any]) -> Any:
    picked = _pick_first(primary, *REFERENCE_IMAGE_KEYS)
    if picked is not None:
        return picked
    return _pick_first(fallback, *REFERENCE_IMAGE_KEYS)


def _reference_image_sources(primary: Mapping[str, Any], fallback: Mapping[str, Any]) -> tuple[Any, ...]:
    sources: list[Any] = []
    explicit_references = _pick_reference_images(primary, fallback)
    if explicit_references is not None:
        sources.append(explicit_references)

    for side_key in SIDE_REFERENCE_IMAGE_KEYS:
        side_reference = _pick_first(primary, side_key)
        if side_reference is None:
            side_reference = _pick_first(fallback, side_key)
        if side_reference is not None:
            sources.append(side_reference)

    return tuple(sources)


def _iter_image_items(raw_value: Any) -> tuple[Any, ...]:
    if raw_value is None:
        return ()
    if isinstance(raw_value, (str, bytes, bytearray, Mapping)):
        return (raw_value,)
    if isinstance(raw_value, Sequence):
        return tuple(raw_value)
    return (raw_value,)


def _stage_reference_images(raw_value: Any) -> tuple[Path, ...]:
    staged: list[Path] = []
    for item in _iter_image_items(raw_value):
        staged_image = _stage_input_image(item)
        if staged_image is not None:
            staged.append(staged_image)
    return tuple(staged)


def _stage_reference_image_sources(raw_values: Sequence[Any]) -> tuple[Path, ...]:
    staged: list[Path] = []
    for raw_value in raw_values:
        staged.extend(_stage_reference_images(raw_value))
    return tuple(staged)


def _sanitize_generation_params(params: Mapping[str, Any]) -> dict[str, Any]:
    image_param_keys = set(REFERENCE_IMAGE_KEYS) | set(SIDE_REFERENCE_IMAGE_KEYS)
    return {key: value for key, value in params.items() if key not in image_param_keys}


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


READINESS_LABELS = {
    "ready": "Ready",
    PREFLIGHT_CODE_CODEX_MISSING: "Setup Codex",
    PREFLIGHT_CODE_NOT_AUTHENTICATED: "Login",
    PREFLIGHT_CODE_NO_ENTITLEMENT: "Login",
    PREFLIGHT_CODE_UNSUPPORTED_VERSION: "Update Extension",
    PREFLIGHT_CODE_UNSUPPORTED_PLATFORM: "Unsupported",
}

SAFE_READINESS_EVIDENCE_FIELDS = (
    "source",
    "runtime_name",
    "runtime_version",
    "auth_state",
    "entitlement_state",
    "platform",
)

SUPPORTED_PLATFORM_KEYS = {
    "darwin/arm64",
    "darwin/x86_64",
    "linux/arm64",
    "linux/x86_64",
    "windows/x86_64",
}

PLATFORM_SUPPORT_STATES = {
    "darwin/arm64": "enabled",
    "darwin/x86_64": "enabled",
    "linux/arm64": "enabled",
    "linux/x86_64": "enabled",
    "windows/x86_64": "experimental",
}

GENERIC_REFRESH_ACTION = {
    "id": "codex.refresh_readiness",
    "kind": "refresh_readiness",
    "label": "Refresh",
    "safety": "non_destructive",
    "refresh_after": "always",
}


def _readiness_label(machine_code: str, ok: bool) -> str:
    if ok:
        return "Ready"
    return READINESS_LABELS.get(machine_code, "Checking failed")


def _safe_readiness_evidence(evidence: Any) -> dict[str, str]:
    safe: dict[str, str] = {}
    for field_name in SAFE_READINESS_EVIDENCE_FIELDS:
        value = getattr(evidence, field_name, None)
        if value is not None:
            safe[field_name] = str(value)
    return safe


def _supported_version_values(supported_version_range: str | None) -> tuple[str, ...]:
    if not supported_version_range:
        return ()
    return tuple(value.strip() for value in supported_version_range.split(",") if value.strip())


def _runtime_version_supported(runtime_version: str | None, supported_version_range: str | None) -> str:
    if not runtime_version or not supported_version_range:
        return "unknown"
    if supported_version_range.startswith(">="):
        return "true"

    supported_versions = _supported_version_values(supported_version_range)
    return "true" if runtime_version in supported_versions else "false"


def _platform_supported(platform_key: str | None) -> str:
    if not platform_key:
        return "unknown"
    return "true" if platform_key in SUPPORTED_PLATFORM_KEYS else "false"


def _platform_support_state(platform_key: str | None) -> str:
    if not platform_key:
        return "unknown"
    return PLATFORM_SUPPORT_STATES.get(platform_key, "unsupported")


def _readiness_diagnostics(report: Any, machine_code: str, checked_at: str) -> dict[str, str]:
    evidence = report.evidence
    runtime_version = getattr(evidence, "runtime_version", None)
    platform_key = getattr(evidence, "platform", None)
    diagnostics: dict[str, str] = {
        "runtime_source": str(getattr(evidence, "source", "local-codex-command")),
        "runtime_version_supported": _runtime_version_supported(runtime_version, report.supported_version_range),
        "platform_supported": _platform_supported(platform_key),
        "platform_support_state": _platform_support_state(platform_key),
        "extension_setup_state": "ready",
        "extension_import_state": "ready",
        "codex_app_server_state": "not_checked",
        "readiness_source": "codex_extension_preflight",
        "diagnostic_status": "ready" if report.ok else "blocked",
        "last_checked_at": checked_at,
    }

    optional_values = {
        "runtime_name": getattr(evidence, "runtime_name", None),
        "runtime_version": runtime_version,
        "supported_versions": report.supported_version_range,
        "platform_key": platform_key,
        "auth_state": getattr(evidence, "auth_state", None),
        "entitlement_state": getattr(evidence, "entitlement_state", None),
    }
    for key, value in optional_values.items():
        if value is not None:
            diagnostics[key] = str(value)

    if machine_code == PREFLIGHT_CODE_UNSUPPORTED_PLATFORM:
        diagnostics["platform_supported"] = "false"
    if machine_code == PREFLIGHT_CODE_UNSUPPORTED_VERSION:
        diagnostics["runtime_version_supported"] = "false"
    if report.ok:
        diagnostics["runtime_version_supported"] = "true"
        diagnostics["platform_supported"] = "true"

    return diagnostics


def _readiness_details(report: Any, machine_code: str, label: str, checked_at: str) -> dict[str, Any]:
    del report, machine_code, label, checked_at
    # Keep the default readiness payload intentionally quiet. Older Modly hosts
    # may render `details` inline in dense extension cards, so verbose
    # diagnostics belong in logs or an explicit future debug surface, not in the
    # normal readiness contract.
    return {}


def _readiness_actions(machine_code: str) -> list[dict[str, Any]]:
    if machine_code == PREFLIGHT_CODE_CODEX_MISSING:
        return [
            {
                "id": "codex.setup.docs",
                "kind": "open_external_url",
                "label": "Open Codex setup docs",
                "safety": "manual",
                "docs_url": CODEX_SETUP_DOCS_URL,
                "refresh_after": "never",
            },
            dict(GENERIC_REFRESH_ACTION),
        ]
    if machine_code == PREFLIGHT_CODE_NOT_AUTHENTICATED:
        return [
            {
                "id": "codex.login.docs",
                "kind": "open_external_url",
                "label": "Open Codex auth docs",
                "safety": "manual",
                "docs_url": CODEX_AUTH_DOCS_URL,
                "refresh_after": "never",
            },
            dict(GENERIC_REFRESH_ACTION),
        ]
    if machine_code == PREFLIGHT_CODE_NO_ENTITLEMENT:
        return [
            {
                "id": "codex.access.docs",
                "kind": "open_external_url",
                "label": "Open Codex access docs",
                "safety": "manual",
                "docs_url": CODEX_ACCESS_DOCS_URL,
                "refresh_after": "never",
            },
            dict(GENERIC_REFRESH_ACTION),
        ]
    if machine_code == PREFLIGHT_CODE_UNSUPPORTED_VERSION:
        return [
            {
                "id": "extension.compatibility.docs",
                "kind": "open_external_url",
                "label": "Open extension changelog",
                "safety": "manual",
                "docs_url": EXTENSION_CHANGELOG_URL,
                "refresh_after": "never",
            },
            dict(GENERIC_REFRESH_ACTION),
        ]
    if machine_code == PREFLIGHT_CODE_UNSUPPORTED_PLATFORM:
        return []
    if machine_code == "ready":
        return [dict(GENERIC_REFRESH_ACTION)]
    return [dict(GENERIC_REFRESH_ACTION)]


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
    reference_image_paths = _stage_reference_image_sources(_reference_image_sources(payload, normalized_params))
    requested_mode = _pick_first(payload, "mode") or _pick_first(normalized_params, "mode")
    if requested_mode == "image-to-image" and input_image_path is None and not reference_image_paths:
        raise build_error(REQUEST_CODE_MISSING_INPUT_IMAGE)

    return GenerateRequest(
        prompt=prompt,
        output_target=output_target,
        input_image_path=input_image_path,
        reference_image_paths=reference_image_paths,
        params=_sanitize_generation_params(normalized_params),
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


class CodexImageGenerator:
    MODEL_ID = "modly-codex-image-extension"
    DISPLAY_NAME = "Codex Local Image Model"
    VRAM_GB = 0

    def __init__(self, model_dir: Path, outputs_dir: Path) -> None:
        self.model_dir = Path(model_dir)
        self.outputs_dir = Path(outputs_dir)
        self._loaded = False
        self.hf_repo: str = ""
        self.hf_skip_prefixes: list[str] = []
        self.download_check: str = ""
        self._params_schema: list[dict[str, Any]] = []

    @classmethod
    def params_schema(cls) -> list[dict[str, Any]]:
        # Returning an empty schema here prevents runner.py from overwriting the
        # node-specific params schema already injected by GeneratorRegistry.
        return []

    def load(self) -> None:
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def readiness_status(self) -> dict[str, Any]:
        report = run_preflight()
        machine_code = "ready" if report.ok else (report.machine_code or "preflight/unknown")
        checked_at = datetime.now(UTC).isoformat()
        label = _readiness_label(machine_code, report.ok)
        status: dict[str, Any] = {
            "ok": report.ok,
            "machine_code": machine_code,
            "label_hint": label,
            "checked_at": checked_at,
        }

        if report.reason:
            status["reason"] = report.reason

        evidence = _safe_readiness_evidence(report.evidence)
        if evidence:
            status["evidence"] = evidence

        status["details"] = _readiness_details(report, machine_code, label, checked_at)
        status["actions"] = _readiness_actions(machine_code)

        return status

    def _resolve_prompt(self, params: Mapping[str, Any]) -> str:
        return _ensure_prompt(_pick_first(params, "prompt", "text", "input"))

    def _resolve_mode(self, image_bytes: bytes, params: Mapping[str, Any]) -> str:
        requested_mode = _pick_first(params, "mode", "node_id", "nodeId")
        if requested_mode == IMAGE_TO_IMAGE_MODE:
            return IMAGE_TO_IMAGE_MODE
        if requested_mode == TEXT_TO_IMAGE_MODE:
            return TEXT_TO_IMAGE_MODE
        return IMAGE_TO_IMAGE_MODE if image_bytes else TEXT_TO_IMAGE_MODE

    def _resolve_output_target(self, params: Mapping[str, Any], mode: str) -> str:
        explicit = _pick_first(params, "output_target", "outputTarget", "output_path", "outputPath", "output")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        return f"codex/{mode}-{uuid.uuid4().hex}.png"

    def _build_payload(self, image_bytes: bytes, params: Mapping[str, Any]) -> dict[str, Any]:
        mode = self._resolve_mode(image_bytes, params)
        payload: dict[str, Any] = {
            "prompt": self._resolve_prompt(params),
            "mode": mode,
            "params": dict(params),
            "output_target": self._resolve_output_target(params, mode),
        }
        if mode == IMAGE_TO_IMAGE_MODE:
            payload["input_image"] = {
                "base64": base64.b64encode(image_bytes).decode("ascii"),
                "media_type": "image/png",
            }
        return payload

    def generate(
        self,
        image_bytes: bytes,
        params: dict[str, Any],
        progress_cb=None,
        cancel_event=None,
    ) -> Path:
        del progress_cb, cancel_event
        output_path = generate(
            self._build_payload(image_bytes, params),
            workspace_root=self.outputs_dir,
        )
        return Path(output_path)


assert CodexImageGenerator.__name__ == GENERATOR_CLASS


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
