# Codex Local Image Model V1

Experimental Modly model extension that lets Modly generate local images through a locally installed, locally authenticated Codex runtime.

In user terms: after the extension is installed in Modly and Codex is already working on the host, Modly can expose a **Codex Local Image Model** for:

- **Text-to-image**: enter a prompt and receive one saved local image.
- **Image-to-image**: provide one primary image plus a prompt and receive one saved local image, with up to three optional reference images routed by Modly's multi-image contract.

The extension returns a single absolute local image path. On the currently validated local Modly host path, that image is intended to be preview-compatible through Modly's image output handling.

## Third-party notice

This project is an independent integration experiment and is **not** affiliated with, endorsed by, or sponsored by OpenAI.

- `Codex`, `ChatGPT`, and `OpenAI` are third-party products, services, and marks belonging to their respective owners.
- Use of any local Codex runtime, ChatGPT entitlement, or related OpenAI service remains subject to the applicable OpenAI terms and product availability.

## Current V1 support state

- **Extension version**: `0.1.4`
- **Support state**: experimental
- **Modly surface owner**: FastAPI model extension
- **Bucket**: `model-managed-setup`
- **Implementation profile**: `python-local-bridge`
- **Setup contract**: user-managed Codex login; extension-managed Python venv, official `openai-codex==0.154.0` SDK with its matching `openai-codex-cli-bin==0.154.0`, and host preflight checks
- **Headless eligibility**: conditional; generation can run through Modly's backend model surfaces, but GitHub install/repair and app-level flows remain outside this extension's headless contract
- **Historical host evidence**: the previous legacy integration generated on `linux/arm64` with `codex-cli 0.122.0`, passed readiness with `0.124.0`, and was smoke-tested once on `windows/x86_64`; this evidence does **not** validate the new official SDK path
- **Current migration status**: **E2E PASS on the validated Linux ARM64 host** with `openai-codex==0.154.0` and `openai-codex-cli-bin==0.154.0`. Runtime setup, health/reload, default-model generation, multi-input generation with explicit `gpt-6-astra`, workspace persistence, HTTP image serving, and visual QA all passed
- **Codex CLI compatibility policy**: minimum `>= 0.122.0` by default; newer versions pass preflight as experimental/unvalidated until smoke evidence records them
- **Configured platform allowlist**: `darwin/arm64`, `darwin/x86_64`, `linux/arm64`, `linux/x86_64`, and `windows/x86_64`; allowlisting is not E2E validation
- **Linux ARM64 risk**: still marked high in metadata because it is validated on the current host path, not proven as a broad portability guarantee
- **Official package evidence**: PyPI publishes `openai-codex==0.154.0`, pins `openai-codex-cli-bin==0.154.0`, and provides a `manylinux_2_17_aarch64` runtime wheel; the SDK wheel and public signatures were inspected in a temporary ARM64 environment

## Requirements and compatibility

Runtime support is intentionally narrower than setup portability. `setup.py` contains platform-aware Python venv handling, but V1 runtime preflight is the source of truth for enabled generation platforms.

| Platform | Runtime status | Notes |
| --- | --- | --- |
| Linux `arm64` | Official 0.154.0 path: **E2E PASS on one validated host** | Setup installed the paired SDK/CLI-bin 0.154.0 runtime; health returned HTTP 200 and reload completed without errors. Job `cefd6d9b-61e1-4901-9082-1837ce2f17f7` verified two image inputs plus explicit `gpt-6-astra`; job `799bf881-2945-483b-9cff-6b8786a3f576` verified one image with the configured default model. Both reached `done` at 100%, persisted valid 1254x1254 PNGs, served them as HTTP 200 `image/png`, and passed visual QA. This remains host-specific evidence, not a broad Linux ARM64 portability claim. |
| Linux `x86_64` | **UNTESTED E2E** | Enabled in preflight; requires setup, login, generation, persistence, and preview evidence on the official 0.154.0 path. |
| macOS `arm64` | **UNTESTED E2E** | Enabled in preflight, with no live smoke for the official SDK path. |
| macOS `x86_64` | **UNTESTED E2E** | Enabled in preflight, with no live smoke for the official SDK path. |
| Windows `x86_64` | Official 0.154.0 path: **UNTESTED E2E** | One historical smoke exists for the retired integration only; it cannot promote the migrated path. |
| Windows `arm64` | Unsupported / fail-closed | Not enabled in V1 preflight. ARM64 requires separate Codex CLI and official SDK smoke evidence before reconsideration. |

### Prerequisites

Before installing or using the extension, the host must already have:

1. A Modly build/runtime that supports Python model extensions through the current extension setup/generation contract.
2. Python `>=3.11` available for the extension environment.
3. A local `codex` executable available on `PATH`.
4. A local Codex session already authenticated with a supported ChatGPT entitlement.
5. A Codex CLI runtime version that passes the extension preflight compatibility policy.
    - Default V1 minimum: `>= 0.122.0`.
    - Override the minimum only when deliberately validating another floor: `CODEX_MIN_SUPPORTED_VERSION=...`.
    - Use strict exact allowlisting only for validation/debugging: `CODEX_SUPPORTED_VERSIONS=0.124.0,...`.
    - If a newer Codex is blocked by `preflight/unsupported_version`, update this extension/configuration before assuming Codex itself needs an update.

The extension setup installs this pinned official SDK release:

```text
openai-codex==0.154.0
```

The official SDK release installs its matching `openai-codex-cli-bin==0.154.0` dependency, so the SDK protocol models and launched CLI stay aligned. This removes the legacy community `codex_app_server`/newer-CLI schema drift that rejected `serviceTier="default"`. The user's existing Codex authentication is reused. The separate read-only preflight still validates the host-visible `codex` command, version, platform, authentication, and entitlement before generation.

## Installation / consumption path

### Install from GitHub

In Modly, open **Models/Extensions → Install from GitHub**, enter this repository URL, and run the extension setup/repair action when prompted. The repository root already contains `manifest.json`, `setup.py`, and `generator.py`; do not select a nested directory.

### Local Modly install path

Use the Modly CLI or app extension flow that stages/applies a local extension directory from this repository. In the currently verified path, local stage/apply installed the extension successfully on the user's host.

This extension expects Modly to run its setup script with Modly's Python-root setup contract:

```text
python setup.py '<json-payload>'
```

The setup payload must include:

- `python_exe`: Python executable Modly wants the extension to use.
- `ext_dir`: absolute path to the extension directory.

Optional compatibility field:

- `openai_codex_spec`: accepted only when it exactly matches `openai-codex==0.154.0`; other values fail closed instead of silently drifting the SDK/CLI pair.

The setup script creates `venv/` inside the extension directory, upgrades packaging tools through the venv Python (`python -m pip`, including `venv/Scripts/python.exe -m pip` on Windows), and installs the pinned official SDK/runtime pair. It does not authenticate, repair accounts, or mutate the user's standalone Codex installation.

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

## Usage

From Modly's generate/workflow surface:

1. Select **Codex Local Image Model**.
2. For text-to-image, provide a non-empty prompt.
3. For image-to-image, connect the primary image and optionally up to three more `image` inputs. Modly sends the primary as the normal multipart/image bytes and the connected secondary images in `params.extra_image_paths`.
4. Optionally pass supported parameters exposed by the node metadata, such as `size`, `quality`, `background`, `strength`, or `model`. Leave `model` empty to use the configured Codex default; a non-empty value is forwarded literally to `thread_start(model=...)`.
5. Run generation.

The extension will:

1. Validate the request.
2. Run preflight checks for local Codex executable, supported platform, supported runtime version, authentication, and entitlement.
3. Call the paired Codex runtime through the official `openai_codex` SDK.
4. Persist one image under the Modly workspace/output target.
5. Return the absolute local image path to Modly.

## Parameters

| Parameter | Nodes | Behavior |
| --- | --- | --- |
| `prompt` | Both | Required generation or edit instruction. |
| `model` | Both | Optional free-form Codex model ID. Empty uses Codex configuration; non-empty is forwarded literally to thread start. |
| `size` | Both | Requested output-size hint. |
| `background` | Both | Requested background hint, such as `auto` or `transparent`, when supported. |
| `quality` | Text-to-image | Requested quality hint. |
| `strength` | Image-to-image | Transformation-strength hint from `0` to `1`. |

Image-to-image also consumes Modly's internal `params.extra_image_paths`; it is transport metadata, not a visible path-entry control.

The official SDK persists complete thread history. Output harvesting considers `imageGeneration` items only; paths attached to `userMessage` or `imageView` items are inputs and must never participate in the single-output count.

Historical generation evidence from the retired integration produced an absolute workspace image path similar to:

```text
<modly-workspace>/Default/codex/text-to-image-<request-id>.png
```

### Advanced reference image params

The image-to-image manifest uses the upstream representation `inputs: ["image", "image", "image", "image"]`. Modly keeps the primary image in the normal generator `image_bytes` argument and sends connected secondary images in `params.extra_image_paths`. Null, empty, and whitespace-only holes are omitted without reordering the remaining paths. Advanced callers may also use the existing `input_images`, `inputImages`, `reference_images`, `referenceImages`, `reference_image_paths`, or `referenceImagePaths` aliases.

Legacy advanced callers using `left_image_path`, `back_image_path`, and `right_image_path` remain compatible. All secondary images are attached after the primary in deterministic order. Image paths and the optional model ID are transport fields: neither is copied into the instruction text.

Each value may be a single item or a list. Supported item shapes are:

- A local file path string.
- A base64 string or `data:image/...;base64,...` data URI.
- A mapping containing `path` or `input_image_path`.
- A mapping containing `base64`, `data`, or `content`, plus optional `media_type` / `mime_type`.

These extra images are attached to the Codex runtime after the primary source image and are treated as visual references. They do not change the single-output contract and are not a claim that Modly owns a native multi-image UI for this extension.

## Output path rules

The extension accepts only **workspace-relative** output targets.

- Empty targets are rejected.
- Absolute external paths are rejected.
- Windows-shaped absolute, UNC, drive-relative, and backslash traversal targets are rejected even on POSIX test hosts.
- Traversal-like paths such as `../foo.png` are rejected.
- Directory targets are allowed; the extension creates a filename inside the directory.
- File targets must end with `.png`, `.jpg`, `.jpeg`, or `.webp`.
- Successful requests return one **absolute local image path** that exists and is readable.

See `docs/decisions/v1-locks.md` for the branch-local `modly-private` image preview assumption and its portability caveat.

## Limitations and V1 scope

### Supported modes

- **Text-to-image**: prompt only.
- **Image-to-image**: prompt plus one valid primary input image, with optional advanced reference image params or Modly-routed generic reference images.

### Out of scope

- Codex installation or login automation.
- Entitlement repair or account management.
- Remote API-key mode or cloud fallback.
- Batch queueing or multi-image outputs.
- Video, audio, or non-image generation.
- App-level GitHub install/repair automation.
- Cross-host preview guarantees outside the validated local Modly host path.
- Codex authentication, account repair, or mutation of a standalone Codex CLI from `setup.py`.
- Promoting any official 0.154.0 platform path to **E2E PASS** without new recorded setup, generation, persistence, and preview evidence.

## Troubleshooting and failure taxonomy

Errors are explicit and machine-coded so Modly or callers can present useful messages.

### Preflight

- `preflight/codex_missing` — `codex` is not available on `PATH`.
- `preflight/not_authenticated` — local Codex authentication could not be verified.
- `preflight/no_entitlement` — a supported ChatGPT entitlement could not be verified.
- `preflight/unsupported_platform` — the host platform is not enabled for V1.
- `preflight/unsupported_version` — the detected Codex version is missing/unparsable, below the minimum, or outside an explicit exact allowlist.

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

## Weights

This extension has no Hugging Face or other model-weight payload. The Modly model-weight download UI and `models/<extension-id>/<node-id>/` storage path are not used. Setup installs only the pinned official Codex SDK/runtime Python packages; Codex service access remains governed by the user's authenticated account.

## Credits

- Extension integration and manifest: **DrHepa**.
- Codex Python SDK and CLI runtime: **OpenAI**, under the upstream Apache-2.0 license.
- Modly host application: **Lightning Pixel**.

See `THIRD_PARTY_NOTICES.md` for dependency attribution. This independent integration is not affiliated with or endorsed by OpenAI.

## License

The extension wrapper is licensed under the repository's `LICENSE` file. Third-party components retain their own licenses; installing or using Codex remains subject to the applicable upstream license and service terms.

## Repo orientation

- `manifest.json` — planned identity, UI metadata, and `nodes` definitions for Modly discovery.
- `setup.py` — Modly setup entrypoint that creates the extension venv and installs `openai-codex==0.154.0` with its matching CLI runtime dependency.
- `generator.py` — Modly-facing orchestration entrypoint.
- `codex_backend/` — Codex adapter, preflight, persistence, contracts, and errors.
- `docs/architecture.md` — module boundaries and recommended implementation order.
- `docs/decisions/v1-locks.md` — locked V1 assumptions and portability caveats.
- `docs/smoke/manual-smoke.md` — optional local manual smoke steps.
- `CHANGELOG.md` — release notes for consumable versions.
