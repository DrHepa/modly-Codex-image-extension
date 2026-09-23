# Manual Smoke: Local Auth Flow

> **Current status:** **E2E PASS on the validated Linux ARM64 host** with `openai-codex==0.154.0` and `openai-codex-cli-bin==0.154.0`. Runtime setup, health/reload, saved-path harvesting, workspace persistence, HTTP image delivery, and visual QA passed for both default-model and multi-input/explicit-model flows. Windows x86_64 remains historical and unvalidated on the official SDK path.

## Purpose
Optional, CI-excluded smoke steps for a developer machine that already has a valid local Codex login and the extension's pinned official `openai-codex` setup path available.

## Preconditions
- Run these steps manually only; they are **not** part of CI.
- Use the intended local host target with the documented branch-local image preview assumption.
- Ensure `codex` is on `PATH`.
- Ensure the local session is authenticated and entitled.
- Use the default minimum Codex CLI compatibility policy (`>= 0.122.0`) unless this smoke is intentionally validating a stricter exact allowlist with `CODEX_SUPPORTED_VERSIONS=<approved-version>`.

## Smoke Steps
1. Create or activate a local Python environment for this repo.
2. Run extension setup so the extension venv installs `openai-codex==0.154.0` and its matching `openai-codex-cli-bin==0.154.0` dependency.
3. Prepare a writable workspace-relative output target such as `outputs/smoke/result.png`.
4. Run a prompt-only request through `generator.py`, passing a non-empty prompt and the workspace-relative output target.
5. Verify the command returns one absolute image path under the workspace and that the file exists.
6. Repeat with one valid primary image plus secondary connected inputs, including a gap, and verify `params.extra_image_paths` preserves connected-image order while omitting the gap.
7. Repeat once with an empty `model` and once with a verified non-empty model ID; confirm the empty value uses Codex configuration and the non-empty value reaches thread start without appearing in instruction text.
8. In the intended local host target, confirm the returned image path is previewed as expected for that branch-local host behavior.

## Recorded Linux ARM64 E2E Evidence

- Runtime setup installed `openai-codex==0.154.0` with `openai-codex-cli-bin==0.154.0`; Modly health returned HTTP 200 and reload completed without errors.
- Multi-input plus explicit-model job `cefd6d9b-61e1-4901-9082-1837ce2f17f7` reached `done` at 100%, sent exactly two image inputs to `gpt-6-astra`, and produced a visually correct 1254x1254 PNG with SHA-256 `488c1d54c292636570b4e8e0627a9894c434cdb3b790387f12d0255a33a7b14c`. Its Modly `output_url` returned HTTP 200 with `Content-Type: image/png`.
- Single-input default-model job `799bf881-2945-483b-9cff-6b8786a3f576` reached `done` at 100%, sent exactly one image input, and produced a visually correct 1254x1254 PNG with SHA-256 `a402d5b894d55e0105e81951c7e23e01d4d6c35166f4713d3e9983209c2d3f92`. Its Modly `output_url` returned HTTP 200 with `Content-Type: image/png`.
- Both jobs exercised the repaired collector: primary/reference paths in `userMessage` and `imageView` items were excluded and one authoritative `imageGeneration.saved_path` was persisted.

This evidence promotes only the tested Linux ARM64 host path. It does not validate other architectures, operating systems, accounts, or future SDK/CLI versions.

## Windows x86_64 Experimental Checklist

Windows `x86_64` has one historical smoke on the retired integration; the official 0.154.0 path is **UNTESTED E2E**. Use this checklist before treating any Windows host as ready for real work:

- [ ] CLI discovery: `codex` is found through the user's PATH/PATHEXT configuration.
- [ ] CLI version: `codex --version` reports a parseable version at or above the default minimum (`>= 0.122.0`), or an exact version from `CODEX_SUPPORTED_VERSIONS` when deliberately testing strict allowlist mode.
- [ ] Read-only auth parse: `codex login status` / `codex auth status` can be parsed without logging in, updating, repairing, or exposing raw auth output.
- [ ] Setup: Modly setup creates the extension venv and uses `venv/Scripts/python.exe -m pip` to install `openai-codex==0.154.0`.
- [ ] SDK import: generation runtime can import `openai_codex` from the extension-managed `venv/Lib/site-packages` even when Modly executes with embedded Python.
- [ ] Text-to-image: one prompt-only request returns one saved image.
- [ ] Image-to-image: one prompt-plus-image request returns one saved image.
- [ ] Workspace output: returned output stays under a workspace-relative target; Windows absolute, UNC, drive-relative, and traversal-shaped targets are rejected.
- [ ] Modly preview: the returned local image path previews in the intended Modly host.

### Windows non-goals

- No Modly core changes unless smoke evidence exposes a host-side blocker.
- No automatic Codex CLI install, update, login, entitlement repair, or account management.
- No official SDK/CLI pair pin change unless compatibility review and smoke evidence require it.
- No Windows `arm64` enablement without separate evidence.
- No broad Windows support claim from the historical smoke; the migrated path needs a fresh checklist and review.

## Failure Checks
- Remove or rename `codex` on `PATH` and confirm preflight fails before generation starts.
- Clear the local auth session and confirm the request fails with an authentication/entitlement reason.
- Use `../escape.png` or `outputs/result.gif` and confirm output validation rejects the request.
- Force a runtime path with no saved image and confirm the extension returns `runtime/no_output` instead of success.

## Notes
- Do not treat this document as proof of cross-host portability.
- Do not automate local login, entitlement repair, or runtime installation as part of V1.
- Keep the official 0.154.0 Windows path **UNTESTED E2E** until a new target-host smoke completes; retain the previous result as historical evidence only.
