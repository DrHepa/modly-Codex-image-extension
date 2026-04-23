# Manual Smoke: Local Auth Flow

## Purpose
Optional, CI-excluded smoke steps for a developer machine that already has a local Codex runtime, a valid local login, and a reviewed `codex_app_server` source/install.

## Preconditions
- Run these steps manually only; they are **not** part of CI.
- Use the intended local host target with the documented branch-local image preview assumption.
- Ensure `codex` is on `PATH`.
- Ensure the local session is authenticated and entitled.
- Set an explicit allowlist, for example: `export CODEX_SUPPORTED_VERSIONS=<approved-version>`.

## Smoke Steps
1. Create or activate a local Python environment for this repo.
2. Install test tooling and the approved `codex_app_server` prerequisite using the team-reviewed source strategy.
3. Prepare a writable workspace-relative output target such as `outputs/smoke/result.png`.
4. Run a prompt-only request through `generator.py`, passing a non-empty prompt and the workspace-relative output target.
5. Verify the command returns one absolute image path under the workspace and that the file exists.
6. Repeat with one valid input image to exercise the prompt-plus-image flow.
7. In the intended local host target, confirm the returned image path is previewed as expected for that branch-local host behavior.

## Failure Checks
- Remove or rename `codex` on `PATH` and confirm preflight fails before generation starts.
- Clear the local auth session and confirm the request fails with an authentication/entitlement reason.
- Use `../escape.png` or `outputs/result.gif` and confirm output validation rejects the request.
- Force a runtime path with no saved image and confirm the extension returns `runtime/no_output` instead of success.

## Notes
- Do not treat this document as proof of cross-host portability.
- Do not automate local login, entitlement repair, or runtime installation as part of V1.
