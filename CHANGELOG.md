# Changelog

## 0.1.4 - 2026-09-23

### Fixed

- Replaces image-input descriptor objects with upstream-compatible `inputs: ["image", "image", "image", "image"]`, avoiding the Modly workflow black screen caused by object entries.
- Reads Modly secondary connections from `params.extra_image_paths`, preserves their order, and omits null/empty gaps while keeping the primary multipart image first.
- Replaces the legacy `codex_app_server_sdk`/external CLI combination with the official pinned `openai-codex==0.154.0` SDK and its matching `openai-codex-cli-bin==0.154.0` runtime, removing the `serviceTier="default"` validation mismatch.
- Pins `0.154.0`, the first verified published compatible SDK release, instead of the unavailable `0.153.4` package version.
- Recovers persisted image-generation output after official `TurnHandle.run()` raises for a failed turn by reading the thread with the retained handle ID before closing Codex.
- Unwraps the official `AbsolutePathBuf` root model before path conversion so saved paths do not become invalid strings such as `root='/tmp/result.png'`.
- Restricts saved-path harvesting from official thread history to `imageGeneration` items, so primary/reference `userMessage` and `imageView` paths cannot be mistaken for multiple generated outputs.

### Added

- Adds an optional free-form `model` parameter to both nodes. Empty uses Codex configuration; non-empty values are passed literally to `thread_start(model=...)` and never embedded in instructions.

### Validation boundary

- Package metadata, real SDK signatures/models, and repository tests are verified on Linux ARM64.
- Linux ARM64 authoritative E2E passed on the official 0.154.0 path: paired SDK/CLI-bin setup, HTTP 200 health, error-free reload, default-model and multi-input/explicit-`gpt-6-astra` jobs, workspace persistence, HTTP 200 `image/png` delivery, and visual QA.
- Multi-input job `cefd6d9b-61e1-4901-9082-1837ce2f17f7` completed at 100% with two image inputs; its 1254x1254 PNG has SHA-256 `488c1d54c292636570b4e8e0627a9894c434cdb3b790387f12d0255a33a7b14c`.
- Default-model job `799bf881-2945-483b-9cff-6b8786a3f576` completed at 100% with one image input; its 1254x1254 PNG has SHA-256 `a402d5b894d55e0105e81951c7e23e01d4d6c35166f4713d3e9983209c2d3f92`.
- Earlier Linux/Windows generation evidence for the retired integration remains historical and does not validate other platforms on the official path.

## 0.1.3 - 2026-05-06

### Fixed

- Treats Modly workflow `left_image_path`, `back_image_path`, and `right_image_path` params as side reference images in deterministic left/back/right order after explicit reference lists.
- Removes named side-image path params before Codex instruction construction so raw local paths are not echoed as text hints.

### Added

- Declares optional image-to-image `front`, `left`, `back`, and `right` manifest inputs while keeping image path params out of the visible params schema.
- Uses neutral user-facing labels for those workflow inputs (`Primary image`, `Image 2`, `Image 3`, `Image 4`) while preserving compatible internal routing handles.

## 0.1.2 - 2026-05-06

### Added

- Adds advanced multi-reference-image request params (`input_images` / `reference_images` aliases) while keeping the visible Modly node UI compact and preserving single-output generation.

## 0.1.1 - 2026-04-29

### Fixed

- Keeps the default Codex CLI compatibility policy as a minimum version gate (`>= 0.122.0`) so newer daily Codex versions such as `0.125.0` pass unless a strict exact allowlist is explicitly configured.
- Changes unsupported-version readiness guidance to point users at extension/config compatibility instead of telling them to update Codex or opening the Codex changelog.

## 0.1.0 - 2026-04-24

### Highlights

- Ships the V1 **Codex Local Image Model** Modly extension for prompt-only text-to-image and prompt-plus-image image-to-image flows.
- Uses a real local Codex runtime path through `codex_app_server`, with generation verified on the current host through ChatGPT-authenticated Codex.
- Installs `codex_app_server` during extension setup from the pinned reviewed source: `git+https://github.com/openai/codex.git@a9f75e5cda2d6ff469a859baf8d2f50b9b04944a#subdirectory=sdk/python`.
- Keeps Modly planned extension identity separate from runtime evidence discovered during preflight.
- Aligns with Modly's V1 `model-managed-setup` contract: users manage Codex install/login/entitlement, while the extension manages its Python venv, SDK bootstrap, request validation, preflight checks, local Codex call, and output persistence.
- Adds readiness actions/status support for Modly host UIs, with placeholder/debug actions removed from the public card surface.
- Uses a default minimum Codex CLI compatibility policy (`>= 0.122.0`) so newer daily CLI builds are not blocked solely for being newer.
- Adds an evidence-gated Windows `x86_64` experimental preflight path for smoke validation; this is **not** a Windows support claim.
- Fixes Windows setup/runtime seams by running pip through the extension venv Python and loading `codex_app_server` from the extension-managed venv when Modly executes with embedded Python.

### Validated path

- Validated locally on `linux/arm64` with `codex-cli 0.122.0`; readiness is also verified with `codex-cli 0.124.0`.
- Smoke-validated on one Windows `x86_64` user host for setup, SDK import, and generation; Windows remains experimental and host-local preflight is still required.
- Verified text-to-image output path shape: `<modly-workspace>/Default/codex/text-to-image-<request-id>.png`.

### Known limitations

- Experimental V1; not a public package readiness claim.
- `codex_app_server` is installed from a pinned direct Git source, not assumed to be a stable public PyPI dependency.
- Private GitHub staging/install through Modly can be blocked by HTTPS credential configuration; local stage/apply is the verified private-development path.
- Headless generation is conditional on a running Modly backend and satisfied local runtime prerequisites; app-level GitHub install/repair flows are outside this extension's headless contract.
- Compatibility defaults to a minimum version gate; `CODEX_SUPPORTED_VERSIONS` remains only for deliberate strict exact allowlist validation/debugging.
- Linux ARM64 remains marked as high risk in metadata because current validation is host-specific, not a broad portability guarantee.
- Windows `x86_64` remains **Experimental / smoke-validated on one host** even though preflight may proceed when all local gates pass; Windows `arm64` remains unsupported/fail-closed.
- Broader Windows validation still requires additional smoke evidence for CLI discovery/version, read-only auth parse, setup, text-to-image, image-to-image, workspace output, and Modly preview across target hosts.
- V1 returns one image only; no batch, multi-output, video, audio, remote API-key, or cloud-fallback modes are included.
