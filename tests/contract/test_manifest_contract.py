from __future__ import annotations

import json
from pathlib import Path

from codex_backend.contracts import PLANNED_BUCKET, PLANNED_MODEL_ID, REQUIRED_MANIFEST_METADATA

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "manifest.json"
RUNTIME_ONLY_KEYS = {
    "runtime_name",
    "runtime_version",
    "auth_state",
    "entitlement_state",
    "platform",
    "runtime_evidence",
    "live_identity",
}


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_declares_one_planned_model_identity() -> None:
    manifest = load_manifest()

    assert manifest["type"] == "model"
    assert manifest["bucket"] == PLANNED_BUCKET

    models = manifest["models"]
    assert len(models) == 1
    assert models[0]["id"] == PLANNED_MODEL_ID
    assert models[0]["identity_resolution"] == "planned"


def test_manifest_includes_required_metadata() -> None:
    manifest = load_manifest()

    assert manifest["metadata"] == dict(REQUIRED_MANIFEST_METADATA)


def test_manifest_separates_planned_identity_from_runtime_evidence() -> None:
    manifest = load_manifest()

    assert RUNTIME_ONLY_KEYS.isdisjoint(manifest)
    assert RUNTIME_ONLY_KEYS.isdisjoint(manifest["metadata"])
    assert RUNTIME_ONLY_KEYS.isdisjoint(manifest["models"][0])
