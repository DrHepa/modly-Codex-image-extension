# V1 Decision Locks

## Status
- **Locked for V1**: accepted Codex runtime evidence source, compatible version policy, extension dependency strategy, planned identity/runtime identity separation, and Python-first subprocess packaging shape.
- **Locked for current V1 host path**: the published official `openai-codex==0.154.0` SDK is paired with `openai-codex-cli-bin==0.154.0` during extension setup.

## Locked: accepted Codex runtime evidence source

V1 accepts **local runtime evidence only** for Codex detection/version reporting:

1. the locally installed `codex` runtime executable must be discoverable on `PATH`, and
2. runtime name/version evidence must come from a direct local command invocation during preflight.

### Why this is locked
- The spec requires runtime evidence to stay separate from planned manifest identity.
- A local command check is the narrowest evidence source that is observable at runtime without inventing cloud or packaging guarantees.

### V1 rule
- `manifest.json` keeps the planned extension identity unchanged.
- Preflight may report detected runtime name/version as **runtime evidence only**.
- Documentation, tests, and later modules must not treat package metadata, README text, or guessed Python dependency versions as authoritative runtime proof.

## Locked: compatible version policy

V1 locks a **conservative compatibility rule**:

- Supported Codex runtime evidence starts at a **minimum supported CLI version** and remains evidence-gated for support promotion.
- Current V1 bootstrap minimum: **`>= 0.122.0`** unless the minimum is explicitly overridden.
- `CODEX_SUPPORTED_VERSIONS` remains available as a deliberate strict exact allowlist for validation/debugging, but it is not the default user-facing gate.

### Current V1 assumption
- Because daily Codex CLI releases can otherwise block newly updated users immediately, the working implementation uses a **minimum version gate** by default.
- Newer versions pass preflight as **experimental/unvalidated**; support claims still require explicit smoke evidence before documentation can promote them.
- The official 0.154.0 SDK/CLI-bin path has authoritative E2E evidence on one Linux ARM64 host: setup, health/reload, default-model generation, multi-input generation with explicit `gpt-6-astra`, persistence, HTTP image serving, and visual QA passed. This is host-specific evidence, not a general portability promotion.
- Windows `x86_64` remains enabled in preflight, but its only smoke evidence belongs to the retired legacy integration; the official 0.154.0 path is **UNTESTED E2E**. Windows `arm64` remains unsupported/fail-closed.
- This is a limited validation gate, not a broad support promotion. Broader support promotion requires more recorded smoke evidence for CLI discovery/version, read-only auth parsing, setup, generation, output persistence, and Modly preview across target hosts.

## Locked: official Codex SDK dependency strategy

V1 locks the published official Python SDK and its matching runtime dependency:

- The extension imports `openai_codex` as its only Python SDK boundary.
- The reviewed extension pin is `openai-codex==0.154.0`.
- That release installs `openai-codex-cli-bin==0.154.0`, preventing the legacy SDK/newer CLI response-schema drift that rejected `serviceTier="default"`.
- PyPI metadata and the downloaded SDK wheel confirm the exact dependency pin; PyPI publishes a `manylinux_2_17_aarch64` CLI runtime wheel for this version.
- The official collector raises from `TurnHandle.run()` when a turn finishes failed, so the adapter retains the handle ID and reads persisted thread items before deciding whether the failure produced a recoverable image.
- Official thread history also contains primary/reference paths in `userMessage` and `imageView` items. Only `imageGeneration` items are authoritative generated-output records; counting generic `path` fields makes a valid single output look like unsupported multi-output.

### Required strategy
- Pin the official SDK in both `pyproject.toml` and `setup.py`.
- Let the SDK use its packaged matching CLI runtime instead of injecting a potentially incompatible `codex_bin`.
- Pass working-directory and sandbox policy through the official `thread_start(cwd=..., sandbox=...)` API.

### Rejected for V1
- Unpinned floating install instructions.
- The former community/legacy `codex_app_server_sdk` dependency.
- Patching legacy Pydantic enums to tolerate a newer CLI schema.
- Floating `openai-codex` installs or a separately drifting CLI override.

## Locked: packaging/bootstrap shape

- Python-first subprocess structure stays in-repo under `codex_backend/`.
- `setup.py` remains present because the approved design targets Modly's subprocess extension flow.
- Runtime dependencies stay explicit and pinned; test extras remain separate.
- `setup.py` must run pip through the platform-correct venv Python (`python -m pip`), including `venv/Scripts/python.exe -m pip` on Windows. It installs only the SDK-owned matching CLI dependency; it must not authenticate, repair accounts, or mutate a standalone Codex CLI installation.

## Locked: identity boundary

- **Planned identity** belongs to extension metadata and remains stable.
- **Live identity** belongs to preflight/runtime evidence and must never overwrite planned identity.

## Documented branch-local host preview assumption

- The intended local host target (`modly-private`) has branch-local evidence that `workflowRunStore.ts` collects `outputType === 'image'` into `nodeImageOutputs`.
- The same local host target has branch-local evidence that `PreviewImageNode.tsx` renders those image outputs.
- For V1 inside this repository, that evidence is sufficient to treat a returned local image path as the intended preview contract for the **target host branch only**.

### Portability caveat
- This is **not** promoted to an upstream or cross-host lock.
- Implementation in this repo may target the documented local host behavior, but must not claim that any other Modly branch, release, or host automatically supports the same preview flow.
- Later documentation/tests must keep framing this as a branch-local compatibility assumption until portability is re-verified elsewhere.

## Assumptions still not promoted to locks

- Future official SDK/CLI versions beyond the reviewed `0.154.0` pair.
- Additional Codex runtime version strings beyond the current minimum policy.
- Windows runtime behavior for the official 0.154.0 path; the single previous `windows/x86_64` smoke is historical only.
- Host preview behavior outside the already documented branch-local observations.

These remain assumptions until later phases add verified implementation evidence and contract tests.
