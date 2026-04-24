# Codex Local Image Model V1

Experimental Modly model extension that lets Modly generate local images through a locally installed, locally authenticated Codex runtime.

In user terms: after the extension is installed in Modly and Codex is already working on the host, Modly can expose a **Codex Local Image Model** for:

- **Text-to-image**: enter a prompt and receive one saved local image.
- **Image-to-image**: provide a source image plus a prompt and receive one saved local image.

The extension returns a single absolute local image path. On the currently validated local Modly host path, that image is intended to be preview-compatible through Modly's image output handling.

## Third-party notice

This project is an independent integration experiment and is **not** affiliated with, endorsed by, or sponsored by OpenAI.

- `Codex`, `ChatGPT`, and `OpenAI` are third-party products, services, and marks belonging to their respective owners.
- Use of any local Codex runtime, ChatGPT entitlement, or related OpenAI service remains subject to the applicable OpenAI terms and product availability.

## Current V1 support state

- **Extension version**: `0.1.0`
- **Support state**: experimental
- **Modly surface owner**: FastAPI model extension
- **Bucket**: `model-managed-setup`
- **Implementation profile**: `python-local-bridge`
- **Setup contract**: user-managed Codex install/login; extension-managed Python venv, pinned `codex_app_server` bootstrap, and preflight checks
- **Headless eligibility**: conditional; generation can run through Modly's backend model surfaces, but GitHub install/repair and app-level flows remain outside this extension's headless contract
- **Validated host path**: `linux/arm64` with `codex-cli 0.122.0`
- **Configured platform allowlist**: `darwin/arm64`, `darwin/x86_64`, `linux/arm64`, `linux/x86_64`
- **Linux ARM64 risk**: still marked high in metadata because it is validated on the current host path, not proven as a broad portability guarantee

## Prerequisites

Before installing or using the extension, the host must already have:

1. A Modly build/runtime that supports Python model extensions through the current extension setup/generation contract.
2. Python `>=3.11` available for the extension environment.
3. A local `codex` executable available on `PATH`.
4. A local Codex session already authenticated with a supported ChatGPT entitlement.
5. A Codex runtime version approved by the extension preflight allowlist.
   - Default V1 lock: `0.122.0`.
   - Override only when deliberately validating another version: `CODEX_SUPPORTED_VERSIONS=...`.

The extension setup installs `codex_app_server` from this pinned reviewed source unless explicitly overridden:

```text
git+https://github.com/openai/codex.git@a9f75e5cda2d6ff469a859baf8d2f50b9b04944a#subdirectory=sdk/python
```

This repo does **not** claim that `codex_app_server` is a stable public PyPI package. The pinned direct-source install is part of the V1 setup contract.

## Installation / consumption path

### Local Modly install path

Use the Modly CLI or app extension flow that stages/applies a local extension directory from this repository. In the currently verified path, local stage/apply installed the extension successfully on the user's host.

This extension expects Modly to run its setup script with Modly's Python-root setup contract:

```text
python setup.py '<json-payload>'
```

The setup payload must include:

- `python_exe`: Python executable Modly wants the extension to use.
- `ext_dir`: absolute path to the extension directory.

Optional override:

- `codex_app_server_source`: replacement source for `codex_app_server` when intentionally reviewing a different source.

The setup script creates `venv/` inside the extension directory, upgrades packaging tools, and installs the pinned `codex_app_server` source.

### GitHub install caveat for private repositories

Private GitHub installation/staging depends on the Modly install flow being able to fetch the repository. The currently observed `modly ext stage github` path fetched via HTTPS and hit credential limitations for a private repo.

That is a Modly/GitHub credential seam, not a Codex generation problem. Local stage/apply remains the verified path for private development until the GitHub credentials are configured or the repository is consumable by the selected Modly install flow.

Do not treat this README as a claim that private GitHub install/repair is fully headless or automatically supported by this extension.

## Verify installation in Modly

Verification requires a running Modly backend or UI. The CLI cannot prove UI availability by itself.

Backend check, when the Modly FastAPI server is reachable:

```bash
MODLY_PORT=8000
curl "http://127.0.0.1:${MODLY_PORT}/model/all"
```

Replace `8000` with the port used by your Modly backend.

Expected evidence:

- A model entry with planned identity `modly-codex-image-extension`.
- Display name `Codex Local Image Model`.
- Nodes/surfaces for `text-to-image` and `image-to-image` when Modly exposes extension node metadata.

UI expectation, when using a Modly app build wired to the same backend:

- The model list/generation surface should show **Codex Local Image Model**.
- Text generation should accept a prompt.
- Image-to-image should accept an input image plus a prompt.

If the backend lists the model but the UI does not show it, debug the Modly UI/backend wiring separately. This extension does not provide app-level UI install or repair automation.

## Basic usage

From Modly's generate/workflow surface:

1. Select **Codex Local Image Model**.
2. For text-to-image, provide a non-empty prompt.
3. For image-to-image, provide one source image and a non-empty prompt.
4. Optionally pass supported parameters exposed by the node metadata, such as `size`, `quality`, `background`, or `strength`.
5. Run generation.

The extension will:

1. Validate the request.
2. Run preflight checks for local Codex executable, supported platform, supported runtime version, authentication, and entitlement.
3. Call the local Codex runtime through `codex_app_server`.
4. Persist one image under the Modly workspace/output target.
5. Return the absolute local image path to Modly.

Verified local generation evidence from the current host:

```text
/home/drhepa/Documentos/Modly/workspace/Default/codex/text-to-image-5eba339eef194816b38faf79a559b966.png
```

## Output path rules

The extension accepts only **workspace-relative** output targets.

- Empty targets are rejected.
- Absolute external paths are rejected.
- Traversal-like paths such as `../foo.png` are rejected.
- Directory targets are allowed; the extension creates a filename inside the directory.
- File targets must end with `.png`, `.jpg`, `.jpeg`, or `.webp`.
- Successful requests return one **absolute local image path** that exists and is readable.

See `docs/decisions/v1-locks.md` for the branch-local `modly-private` image preview assumption and its portability caveat.

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
- Public package readiness claims for `codex_app_server`.
- App-level GitHub install/repair automation.
- Cross-host preview guarantees outside the validated local Modly host path.

## Failure taxonomy

Errors are explicit and machine-coded so Modly or callers can present useful messages.

### Preflight

- `preflight/codex_missing` — `codex` is not available on `PATH`.
- `preflight/not_authenticated` — local Codex authentication could not be verified.
- `preflight/no_entitlement` — a supported ChatGPT entitlement could not be verified.
- `preflight/unsupported_platform` — the host platform is not enabled for V1.
- `preflight/unsupported_version` — the detected Codex version is not in the allowlist.

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

- `manifest.json` — planned identity, UI metadata, and `nodes` definitions for Modly discovery.
- `setup.py` — Modly setup entrypoint that creates the extension venv and installs the pinned `codex_app_server` source.
- `generator.py` — Modly-facing orchestration entrypoint.
- `codex_backend/` — Codex adapter, preflight, persistence, contracts, and errors.
- `docs/architecture.md` — module boundaries and recommended implementation order.
- `docs/decisions/v1-locks.md` — locked V1 assumptions and portability caveats.
- `docs/smoke/manual-smoke.md` — optional local manual smoke steps.
- `CHANGELOG.md` — release notes for consumable versions.
