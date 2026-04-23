from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

EXTENSION_ID = "modly-codex-image-extension"
GENERATOR_CLASS = "CodexImageGenerator"
TEXT_TO_IMAGE_NODE_ID = "text-to-image"
IMAGE_TO_IMAGE_NODE_ID = "image-to-image"
PLANNED_NODE_IDS = (TEXT_TO_IMAGE_NODE_ID, IMAGE_TO_IMAGE_NODE_ID)
PLANNED_BUCKET = "model-managed-setup"
IMPLEMENTATION_PROFILE = "python-local-bridge"
SETUP_CONTRACT = "user-managed Codex install+login, extension-managed preflight"
SUPPORT_STATE = "experimental"
SURFACE_OWNER = "FastAPI model extension"
HEADLESS_ELIGIBLE = "conditional"
LINUX_ARM64_RISK = "high"
EXTENSION_AUTHOR = "DrHepa"
EXTENSION_DESCRIPTION = (
    "Experimental local Codex image model extension for text-to-image and image-to-image workflows."
)

RUNTIME_EVIDENCE_SOURCE = "local-codex-command"

TEXT_TO_IMAGE_MODE = "text-to-image"
IMAGE_TO_IMAGE_MODE = "image-to-image"
SUPPORTED_GENERATION_MODES = (TEXT_TO_IMAGE_MODE, IMAGE_TO_IMAGE_MODE)
PREVIEWABLE_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")

ERROR_NAMESPACE_PREFLIGHT = "preflight"
ERROR_NAMESPACE_REQUEST = "request"
ERROR_NAMESPACE_RUNTIME = "runtime"
ERROR_NAMESPACE_OUTPUT = "output"

PREFLIGHT_CODE_CODEX_MISSING = "preflight/codex_missing"
PREFLIGHT_CODE_NOT_AUTHENTICATED = "preflight/not_authenticated"
PREFLIGHT_CODE_NO_ENTITLEMENT = "preflight/no_entitlement"
PREFLIGHT_CODE_UNSUPPORTED_PLATFORM = "preflight/unsupported_platform"
PREFLIGHT_CODE_UNSUPPORTED_VERSION = "preflight/unsupported_version"

REQUEST_CODE_INVALID_PROMPT = "request/invalid_prompt"
REQUEST_CODE_MISSING_INPUT_IMAGE = "request/missing_input_image"
REQUEST_CODE_INVALID_INPUT_IMAGE = "request/invalid_input_image"
REQUEST_CODE_INVALID_OUTPUT_TARGET = "request/invalid_output_target"

RUNTIME_CODE_CALL_FAILED = "runtime/call_failed"
RUNTIME_CODE_MULTI_OUTPUT = "runtime/multi_output_not_supported"
RUNTIME_CODE_NO_OUTPUT = "runtime/no_output"

OUTPUT_CODE_INVALID_TARGET = "output/invalid_target"
OUTPUT_CODE_UNSUPPORTED_EXTENSION = "output/unsupported_extension"
OUTPUT_CODE_PERSIST_FAILED = "output/persist_failed"

REQUIRED_MANIFEST_METADATA: Mapping[str, str] = {
    "resolution": "planned",
    "implementation_profile": IMPLEMENTATION_PROFILE,
    "setup_contract": SETUP_CONTRACT,
    "support_state": SUPPORT_STATE,
    "surface_owner": SURFACE_OWNER,
    "headless_eligible": HEADLESS_ELIGIBLE,
    "linux_arm64_risk": LINUX_ARM64_RISK,
}


class CodexExtensionError(RuntimeError):
    def __init__(self, machine_code: str, message: str) -> None:
        super().__init__(message)
        self.machine_code = machine_code
        self.message = message

    def __str__(self) -> str:
        return f"{self.machine_code}: {self.message}"


@dataclass(frozen=True, slots=True)
class GenerateRequest:
    prompt: str
    output_target: Path
    input_image_path: Path | None = None
    params: Mapping[str, Any] = field(default_factory=dict)

    @property
    def mode(self) -> str:
        return IMAGE_TO_IMAGE_MODE if self.input_image_path else TEXT_TO_IMAGE_MODE


@dataclass(frozen=True, slots=True)
class RuntimeEvidence:
    source: str = RUNTIME_EVIDENCE_SOURCE
    runtime_name: str | None = None
    runtime_version: str | None = None
    runtime_executable: str | None = None
    runtime_version_source: str | None = None
    auth_state: str | None = None
    auth_reason: str | None = None
    entitlement_state: str | None = None
    platform: str | None = None


@dataclass(frozen=True, slots=True)
class PreflightReport:
    ok: bool
    evidence: RuntimeEvidence = field(default_factory=RuntimeEvidence)
    machine_code: str | None = None
    reason: str | None = None
    supported_version_range: str | None = None


@dataclass(frozen=True, slots=True)
class CodexResult:
    saved_path: Path | None
    media_type: str = "image"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    machine_code: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedOutput:
    final_abs_path: Path
    workspace_rel_path: Path
    requested_target: Path
    media_type: str = "image"
