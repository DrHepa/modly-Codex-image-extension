# Architecture Summary

## Intent

This repository keeps Modly integration thin and pushes Codex-specific behavior into `codex_backend/` so planned extension identity, runtime evidence, preflight policy, and output persistence stay separable.

## Module boundaries

### `generator.py`
Owns the Modly-facing entrypoint only.

- Parses request payloads.
- Normalizes prompt, optional input image, and output target.
- Stages temporary input-image files when needed.
- Runs preflight before any Codex call.
- Calls the adapter for text-to-image or image-to-image.
- Persists exactly one returned image into a validated workspace-relative target.
- Returns one absolute output path or raises one mapped extension error.

`generator.py` should NOT grow Codex install/auth/version logic or direct filesystem policy beyond orchestration.

### `codex_backend/contracts.py`
Shared constants, metadata values, dataclasses, generation modes, previewable extensions, and machine-code namespaces.

### `codex_backend/preflight.py`
Runtime/environment boundary.

- Detects supported platform.
- Finds the `codex` executable.
- Reads runtime version evidence.
- Verifies authenticated and entitled session state.
- Returns structured `PreflightReport` data without mutating planned manifest identity.

### `codex_backend/adapter.py`
Single `codex_app_server` integration boundary.

- Resolves supported text-to-image and image-to-image call shapes.
- Normalizes raw Codex responses into one `CodexResult`.
- Attaches runtime module evidence as metadata only.

No other module should call `codex_app_server` directly.

### `codex_backend/persistence.py`
Workspace-path contract boundary.

- Rejects absolute and traversal-like output targets.
- Resolves directory vs file destinations.
- Enforces preview-compatible image extensions.
- Copies the generated image into the requested workspace location.

### `codex_backend/errors.py`
Maps machine codes to actionable user-facing messages, optionally enriched with runtime evidence.

## Identity and evidence split

- **Planned identity** lives in `manifest.json` and remains stable.
- **Live runtime evidence** comes from preflight and adapter metadata.
- Runtime evidence must never overwrite the planned model identity.

## Recommended `sdd-apply` batch order

For this repo, the safest implementation order is:

1. **Decision locks and foundation** — freeze assumptions before code spreads them.
2. **Manifest and identity contract** — lock planned identity before runtime evidence exists.
3. **Core backend contracts** — implement `contracts.py`, `preflight.py`, `persistence.py`, `adapter.py`, then `generator.py`.
4. **Errors and runtime evidence** — centralize failure semantics and preserve identity separation.
5. **Verification** — add unit, integration, and contract coverage against the locked behavior.
6. **Documentation and handoff** — write repo-facing docs after the executable boundaries are stable.

Inside Phase 3 specifically, keep this order:

1. `codex_backend/contracts.py`
2. `codex_backend/preflight.py`
3. `codex_backend/persistence.py`
4. `codex_backend/adapter.py`
5. `generator.py`

That order matters because `generator.py` is orchestration glue; it should consume stable contracts and boundaries rather than invent them inline.

## Practical rule for future changes

If a change affects request parsing or Modly IO, start in `generator.py`. If it affects Codex detection, runtime calls, path policy, or error semantics, change the dedicated `codex_backend/*` module first and keep `generator.py` thin.
