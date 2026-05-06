# Changelog

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
