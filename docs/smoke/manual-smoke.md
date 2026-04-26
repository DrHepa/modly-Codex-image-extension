# Manual Smoke: Local Auth Flow

## Purpose
Optional, CI-excluded smoke steps for a developer machine that already has a local Codex runtime, a valid local login, and the extension's reviewed pinned `codex_app_server` setup path available.

## Preconditions
- Run these steps manually only; they are **not** part of CI.
- Use the intended local host target with the documented branch-local image preview assumption.
- Ensure `codex` is on `PATH`.
- Ensure the local session is authenticated and entitled.
- Use the default minimum Codex CLI compatibility policy (`>= 0.122.0`) unless this smoke is intentionally validating a stricter exact allowlist with `CODEX_SUPPORTED_VERSIONS=<approved-version>`.

## Smoke Steps
1. Create or activate a local Python environment for this repo.
2. Run extension setup so the extension venv installs the pinned `codex_app_server` source snapshot, or override it explicitly only when reviewing a replacement source.
3. Prepare a writable workspace-relative output target such as `outputs/smoke/result.png`.
4. Run a prompt-only request through `generator.py`, passing a non-empty prompt and the workspace-relative output target.
5. Verify the command returns one absolute image path under the workspace and that the file exists.
6. Repeat with one valid input image to exercise the prompt-plus-image flow.
7. In the intended local host target, confirm the returned image path is previewed as expected for that branch-local host behavior.

## Windows x86_64 Experimental Checklist

Windows `x86_64` is **Experimental / smoke-validated on one host**. Use this checklist for each additional Windows host before treating that host as ready for real work:

- [ ] CLI discovery: `codex` is found through the user's PATH/PATHEXT configuration.
- [ ] CLI version: `codex --version` reports a parseable version at or above the default minimum (`>= 0.122.0`), or an exact version from `CODEX_SUPPORTED_VERSIONS` when deliberately testing strict allowlist mode.
- [ ] Read-only auth parse: `codex login status` / `codex auth status` can be parsed without logging in, updating, repairing, or exposing raw auth output.
- [ ] Setup: Modly setup creates the extension venv and uses `venv/Scripts/python.exe -m pip` to install the pinned `codex_app_server` source.
- [ ] SDK import: generation runtime can import `codex_app_server` from the extension-managed `venv/Lib/site-packages` even when Modly executes with embedded Python.
- [ ] Text-to-image: one prompt-only request returns one saved image.
- [ ] Image-to-image: one prompt-plus-image request returns one saved image.
- [ ] Workspace output: returned output stays under a workspace-relative target; Windows absolute, UNC, drive-relative, and traversal-shaped targets are rejected.
- [ ] Modly preview: the returned local image path previews in the intended Modly host.

### Windows non-goals

- No Modly core changes unless smoke evidence exposes a host-side blocker.
- No automatic Codex CLI install, update, login, entitlement repair, or account management.
- No `codex_app_server` pin change unless smoke evidence requires it.
- No Windows `arm64` enablement without separate evidence.
- No broad Windows support claim beyond the smoke-validated host until additional target-host checklists are completed and reviewed.

## Failure Checks
- Remove or rename `codex` on `PATH` and confirm preflight fails before generation starts.
- Clear the local auth session and confirm the request fails with an authentication/entitlement reason.
- Use `../escape.png` or `outputs/result.gif` and confirm output validation rejects the request.
- Force a runtime path with no saved image and confirm the extension returns `runtime/no_output` instead of success.

## Notes
- Do not treat this document as proof of cross-host portability.
- Do not automate local login, entitlement repair, or runtime installation as part of V1.
- Keep Windows status as **Experimental / smoke-validated on one host** until broader target-host evidence justifies promotion.
