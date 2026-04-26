# V1 Decision Locks

## Status
- **Locked for V1**: accepted Codex runtime evidence source, compatible version policy, extension dependency strategy, planned identity/runtime identity separation, and Python-first subprocess packaging shape.
- **Locked for current V1 host path**: a reviewed pinned direct-source install is used to acquire `codex_app_server` during extension setup.

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
- Windows `x86_64` is enabled as an **Experimental / smoke-validated on one host** preflight path; Windows `arm64` remains unsupported/fail-closed.
- This is a limited validation gate, not a broad support promotion. Broader support promotion requires more recorded smoke evidence for CLI discovery/version, read-only auth parsing, setup, generation, output persistence, and Modly preview across target hosts.

## Locked: `codex_app_server` dependency strategy

V1 locks a **conservative source-based strategy** for `codex_app_server`:

- The extension code may depend on `codex_app_server` as a Python import boundary.
- This repository does **not** currently treat `codex_app_server` as a proven public PyPI dependency.
- Therefore V1 must **not** assume `pip install codex_app_server` is sufficient or stable.

### Required strategy
- Keep `codex_app_server` out of hard runtime installation requirements in `pyproject.toml` for now.
- Use a **pinned direct-source install reference** backed by a reviewed upstream location.
- Current reviewed source pin: `git+https://github.com/openai/codex.git@a9f75e5cda2d6ff469a859baf8d2f50b9b04944a#subdirectory=sdk/python`.
- The adapter must pass `AppServerConfig(codex_bin=...)` explicitly because the source install does not include the published pinned runtime package.

### Rejected for V1
- Unpinned floating install instructions.
- Hand-wavy "install whatever `codex_app_server` version exists" guidance.
- Declaring a PyPI dependency without public packaging proof.

## Locked: packaging/bootstrap shape

- Python-first subprocess structure stays in-repo under `codex_backend/`.
- `setup.py` remains present because the approved design targets Modly's subprocess extension flow.
- Initial bootstrap dependencies stay minimal: setuptools-based packaging plus test extras only.
- `setup.py` must run pip through the platform-correct venv Python (`python -m pip`), including `venv/Scripts/python.exe -m pip` on Windows, and must not install, update, authenticate, or repair the Codex CLI.

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

- Exact upstream source location for `codex_app_server`.
- Additional Codex runtime version strings beyond the current minimum policy.
- Broader Windows runtime behavior beyond the single smoke-validated `windows/x86_64` host.
- Host preview behavior outside the already documented branch-local observations.

These remain assumptions until later phases add verified implementation evidence and contract tests.
