# V1 Decision Locks

## Status
- **Locked for V1**: accepted Codex runtime evidence source, compatible version policy, extension dependency strategy, planned identity/runtime identity separation, and Python-first subprocess packaging shape.
- **Documented assumption only**: a compatible local Codex installation plus `codex_app_server` source remains obtainable by the user/team outside this repository; V1 does not automate acquisition.

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

- Supported Codex runtime evidence: **only the exact local runtime major version(s) explicitly approved by this repository's tests/docs at implementation time**.
- Current V1 bootstrap approval: **no open semantic version range is granted yet**.
- Until integration/preflight work proves more, later implementation must treat compatibility as an **allowlist check backed by direct runtime evidence**, not a permissive `>=` range.

### Current V1 assumption
- Because this repository does not yet contain verified runtime fixtures or published compatibility data, the first working implementation may begin with a **single locked runtime evidence string or curated allowlist**.
- Expanding that allowlist requires an explicit update to this document.

## Locked: `codex_app_server` dependency strategy

V1 locks a **conservative source-based strategy** for `codex_app_server`:

- The extension code may depend on `codex_app_server` as a Python import boundary.
- This repository does **not** currently treat `codex_app_server` as a proven public PyPI dependency.
- Therefore V1 must **not** assume `pip install codex_app_server` is sufficient or stable.

### Required strategy
- Keep `codex_app_server` out of hard runtime installation requirements in `pyproject.toml` for now.
- Treat acquisition as a **documented external prerequisite** until the project pins a provable source snapshot.
- When the adapter is implemented, dependency wiring must support one of these explicit strategies only:
  - a vendored source snapshot committed into the repo, or
  - a pinned direct-source install reference backed by a reviewed upstream location.

### Rejected for V1
- Unpinned floating install instructions.
- Hand-wavy "install whatever `codex_app_server` version exists" guidance.
- Declaring a PyPI dependency without public packaging proof.

## Locked: packaging/bootstrap shape

- Python-first subprocess structure stays in-repo under `codex_backend/`.
- `setup.py` remains present because the approved design targets Modly's subprocess extension flow.
- Initial bootstrap dependencies stay minimal: setuptools-based packaging plus test extras only.

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
- Exact Codex runtime version strings that should be allowlisted.
- Host preview behavior outside the already documented branch-local observations.

These remain assumptions until later phases add verified implementation evidence and contract tests.
