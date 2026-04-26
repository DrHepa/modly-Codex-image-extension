from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import (
    OUTPUT_CODE_INVALID_TARGET,
    OUTPUT_CODE_PERSIST_FAILED,
    OUTPUT_CODE_UNSUPPORTED_EXTENSION,
    PREFLIGHT_CODE_CODEX_MISSING,
    PREFLIGHT_CODE_NOT_AUTHENTICATED,
    PREFLIGHT_CODE_NO_ENTITLEMENT,
    PREFLIGHT_CODE_UNSUPPORTED_PLATFORM,
    PREFLIGHT_CODE_UNSUPPORTED_VERSION,
    REQUEST_CODE_INVALID_INPUT_IMAGE,
    REQUEST_CODE_INVALID_OUTPUT_TARGET,
    REQUEST_CODE_INVALID_PROMPT,
    REQUEST_CODE_MISSING_INPUT_IMAGE,
    RUNTIME_CODE_CALL_FAILED,
    RUNTIME_CODE_MULTI_OUTPUT,
    RUNTIME_CODE_NO_OUTPUT,
    CodexExtensionError,
    RuntimeEvidence,
)

DEFAULT_ERROR_MESSAGES: Mapping[str, str] = {
    PREFLIGHT_CODE_CODEX_MISSING: "Codex was not found on PATH. Install the local Codex runtime first, then retry.",
    PREFLIGHT_CODE_NOT_AUTHENTICATED: "Codex authentication could not be verified. Sign in locally and confirm auth status before retrying.",
    PREFLIGHT_CODE_NO_ENTITLEMENT: "The current Codex session does not expose a supported ChatGPT entitlement. Switch to an entitled account and retry.",
    PREFLIGHT_CODE_UNSUPPORTED_PLATFORM: "This host platform is outside the approved V1 support matrix. Use a supported platform before retrying.",
    PREFLIGHT_CODE_UNSUPPORTED_VERSION: "The detected Codex runtime version is below the minimum supported version, unparsable, or outside the explicit CODEX_SUPPORTED_VERSIONS allowlist.",
    REQUEST_CODE_INVALID_PROMPT: "Prompt must be provided as a non-empty string.",
    REQUEST_CODE_MISSING_INPUT_IMAGE: "Image-to-image requests require one valid input image.",
    REQUEST_CODE_INVALID_INPUT_IMAGE: "Input image must be a readable file path or valid base64 image payload.",
    REQUEST_CODE_INVALID_OUTPUT_TARGET: "Output target must be a non-empty workspace-relative path.",
    RUNTIME_CODE_CALL_FAILED: "The Codex runtime call failed before a usable image result was returned. Verify the local runtime and extension prerequisites, then retry.",
    RUNTIME_CODE_MULTI_OUTPUT: "V1 supports exactly one output image. Reconfigure the local runtime to persist a single image result and retry.",
    RUNTIME_CODE_NO_OUTPUT: "Codex did not return a saved image path. Retry after confirming the local runtime can persist one image output.",
    OUTPUT_CODE_INVALID_TARGET: "Output target is outside the workspace contract. Use a workspace-relative file or directory path.",
    OUTPUT_CODE_UNSUPPORTED_EXTENSION: "Output images must use one of: .png, .jpg, .jpeg, or .webp.",
    OUTPUT_CODE_PERSIST_FAILED: "The generated image could not be copied into the requested output target. Verify the source image exists and the destination is writable.",
}


def runtime_evidence_dict(evidence: RuntimeEvidence | None) -> dict[str, Any]:
    if evidence is None:
        return {}

    return {
        key: value
        for key, value in {
            "source": evidence.source,
            "runtime_name": evidence.runtime_name,
            "runtime_version": evidence.runtime_version,
            "runtime_executable": evidence.runtime_executable,
            "runtime_version_source": evidence.runtime_version_source,
            "auth_state": evidence.auth_state,
            "auth_reason": evidence.auth_reason,
            "entitlement_state": evidence.entitlement_state,
            "platform": evidence.platform,
        }.items()
        if value is not None
    }


def resolve_error_message(
    machine_code: str,
    *,
    detail: str | None = None,
    evidence: RuntimeEvidence | None = None,
) -> str:
    base_message = DEFAULT_ERROR_MESSAGES.get(machine_code, "The extension failed with an unmapped machine code.")
    extras: list[str] = []

    if detail:
        extras.append(detail.strip())

    evidence_data = runtime_evidence_dict(evidence)
    evidence_parts = []
    if runtime_name := evidence_data.get("runtime_name"):
        evidence_parts.append(f"runtime={runtime_name}")
    if runtime_version := evidence_data.get("runtime_version"):
        evidence_parts.append(f"version={runtime_version}")
    if auth_state := evidence_data.get("auth_state"):
        evidence_parts.append(f"auth={auth_state}")
    if entitlement_state := evidence_data.get("entitlement_state"):
        evidence_parts.append(f"entitlement={entitlement_state}")
    if platform := evidence_data.get("platform"):
        evidence_parts.append(f"platform={platform}")
    if evidence_parts:
        extras.append("Runtime evidence: " + ", ".join(evidence_parts) + ".")

    if not extras:
        return base_message
    return f"{base_message} {' '.join(extras)}"


def build_error(
    machine_code: str,
    *,
    detail: str | None = None,
    evidence: RuntimeEvidence | None = None,
) -> CodexExtensionError:
    return CodexExtensionError(
        machine_code,
        resolve_error_message(machine_code, detail=detail, evidence=evidence),
    )


__all__ = ["DEFAULT_ERROR_MESSAGES", "build_error", "resolve_error_message", "runtime_evidence_dict"]
