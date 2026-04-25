# Changelog

## 0.1.0 - 2026-04-24

### Highlights

- Ships the V1 **Codex Local Image Model** Modly extension for prompt-only text-to-image and prompt-plus-image image-to-image flows.
- Uses a real local Codex runtime path through `codex_app_server`, with generation verified on the current host through ChatGPT-authenticated Codex.
- Installs `codex_app_server` during extension setup from the pinned reviewed source: `git+https://github.com/openai/codex.git@a9f75e5cda2d6ff469a859baf8d2f50b9b04944a#subdirectory=sdk/python`.
- Keeps Modly planned extension identity separate from runtime evidence discovered during preflight.
- Aligns with Modly's V1 `model-managed-setup` contract: users manage Codex install/login/entitlement, while the extension manages its Python venv, SDK bootstrap, request validation, preflight checks, local Codex call, and output persistence.
- Adds readiness actions/status support for Modly host UIs, with placeholder/debug actions removed from the public card surface.
- Expands the default Codex CLI allowlist to `0.122.0` and `0.124.0`.
- Adds an evidence-gated Windows `x86_64` experimental preflight path for smoke validation; this is **not** a Windows support claim.

### Validated path

- Validated locally on `linux/arm64` with `codex-cli 0.122.0`; readiness is also verified with `codex-cli 0.124.0`.
- Verified text-to-image output path shape: `<modly-workspace>/Default/codex/text-to-image-<request-id>.png`.

### Known limitations

- Experimental V1; not a public package readiness claim.
- `codex_app_server` is installed from a pinned direct Git source, not assumed to be a stable public PyPI dependency.
- Private GitHub staging/install through Modly can be blocked by HTTPS credential configuration; local stage/apply is the verified private-development path.
- Headless generation is conditional on a running Modly backend and satisfied local runtime prerequisites; app-level GitHub install/repair flows are outside this extension's headless contract.
- Compatibility remains allowlist-based. The default approved Codex runtime versions are `0.122.0` and `0.124.0` unless `CODEX_SUPPORTED_VERSIONS` is deliberately overridden.
- Linux ARM64 remains marked as high risk in metadata because current validation is host-specific, not a broad portability guarantee.
- Windows `x86_64` remains **Experimental / pending validation** even though preflight may proceed when all local gates pass; Windows `arm64` remains unsupported/fail-closed.
- Windows validation still requires manual smoke evidence for CLI discovery/version, read-only auth parse, setup, text-to-image, image-to-image, workspace output, and Modly preview.
- V1 returns one image only; no batch, multi-output, video, audio, remote API-key, or cloud-fallback modes are included.
