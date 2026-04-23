# Codex Local Image Model V1

Experimental Modly model extension that turns a prompt, with an optional reference image, into one saved local image path by calling a locally installed and locally authenticated Codex runtime through `codex_app_server`.

## Third-party notice

This project is an independent integration experiment and is **not** affiliated with, endorsed by, or sponsored by OpenAI.

- `Codex`, `ChatGPT`, and `OpenAI` are third-party products, services, and marks belonging to their respective owners.
- Use of any local Codex runtime, ChatGPT entitlement, or related OpenAI service remains subject to the applicable OpenAI terms and product availability.

## V1 scope

### Supported modes
- **Text-to-image**: prompt only.
- **Image-to-image**: prompt plus one valid input image.

### Out of scope
- Codex installation or login automation.
- Entitlement repair or account management.
- Remote API-key mode or cloud fallback.
- Batch queueing or multi-image outputs.
- Video, audio, or non-image generation.
- Release, repair, or host-side workflow automation.

## Prerequisites

- Python environment compatible with this repo's subprocess extension shape.
- Local `codex` executable available on `PATH`.
- Local Codex session already authenticated with a supported ChatGPT entitlement.
- `codex_app_server` available through the externally managed acquisition path documented in `docs/decisions/v1-locks.md`.
- Supported host platform for V1: `darwin/arm64`, `darwin/x86_64`, or `linux/x86_64`.
- Approved Codex runtime version explicitly allowlisted through `CODEX_SUPPORTED_VERSIONS` or an equivalent caller-provided allowlist.

## Setup contract

V1 is intentionally **model-managed-setup**, not self-installing.

- **User-managed**: Codex install, Codex login, and entitlement availability.
- **Extension-managed**: preflight checks for executable presence, supported platform, approved runtime version, authentication state, entitlement state, and output-target validity.

Planned extension identity stays in `manifest.json`. Any detected runtime name/version is runtime evidence only and MUST NOT replace planned identity.

## Output path rules

The extension accepts only **workspace-relative** output targets.

- Empty targets are rejected.
- Absolute external paths are rejected.
- Traversal-like paths such as `../foo.png` are rejected.
- Directory targets are allowed; the extension creates a filename inside the directory.
- File targets must end with `.png`, `.jpg`, `.jpeg`, or `.webp`.
- Successful requests return one **absolute local image path** that exists, is readable, and is intended to be preview-compatible for the documented local target host assumption.

See `docs/decisions/v1-locks.md` for the branch-local `modly-private` image preview assumption and its portability caveat.

## Failure taxonomy

Errors are explicit and machine-coded:

### Preflight
- `preflight/codex_missing`
- `preflight/not_authenticated`
- `preflight/no_entitlement`
- `preflight/unsupported_platform`
- `preflight/unsupported_version`

### Request validation
- `request/invalid_prompt`
- `request/missing_input_image`
- `request/invalid_input_image`
- `request/invalid_output_target`

### Runtime
- `runtime/call_failed`
- `runtime/multi_output_not_supported`
- `runtime/no_output`

### Output persistence
- `output/invalid_target`
- `output/unsupported_extension`
- `output/persist_failed`

Human-readable messaging for these codes lives in `codex_backend/errors.py`.

## Repo orientation

- `manifest.json` — planned identity and required metadata.
- `generator.py` — Modly-facing orchestration entrypoint.
- `codex_backend/` — Codex adapter, preflight, persistence, contracts, and errors.
- `docs/architecture.md` — module boundaries and recommended implementation order.
- `docs/decisions/v1-locks.md` — locked V1 assumptions and portability caveats.
- `docs/smoke/manual-smoke.md` — optional local manual smoke steps.

## Current support state

- **Resolution**: planned
- **Implementation profile**: python-local-bridge
- **Setup contract**: user-managed Codex install+login, extension-managed preflight
- **Support state**: experimental
- **Surface owner**: FastAPI model extension
- **Headless eligible**: conditional
- **Linux ARM64 risk**: high
