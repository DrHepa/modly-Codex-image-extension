from __future__ import annotations

import json
from pathlib import Path

from codex_backend.contracts import (
    EXTENSION_AUTHOR,
    EXTENSION_DESCRIPTION,
    GENERATOR_CLASS,
    IMAGE_TO_IMAGE_NODE_ID,
    PLANNED_BUCKET,
    PLANNED_NODE_IDS,
    REQUIRED_MANIFEST_METADATA,
    TEXT_TO_IMAGE_NODE_ID,
)

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


def test_manifest_declares_planned_nodes_for_each_supported_mode() -> None:
    manifest = load_manifest()

    assert manifest["type"] == "model"
    assert manifest["bucket"] == PLANNED_BUCKET
    assert manifest["generator_class"] == GENERATOR_CLASS
    assert manifest["description"] == EXTENSION_DESCRIPTION
    assert manifest["author"] == EXTENSION_AUTHOR

    nodes = manifest["nodes"]
    assert [node["id"] for node in nodes] == list(PLANNED_NODE_IDS)
    assert nodes[0]["input"] == "text"
    assert nodes[0]["output"] == "image"
    assert nodes[1]["input"] == "image"
    assert nodes[1]["output"] == "image"
    assert all(node["identity_resolution"] == "planned" for node in nodes)


def test_manifest_includes_required_metadata() -> None:
    manifest = load_manifest()

    assert manifest["metadata"] == dict(REQUIRED_MANIFEST_METADATA)


def test_manifest_separates_planned_identity_from_runtime_evidence() -> None:
    manifest = load_manifest()

    assert RUNTIME_ONLY_KEYS.isdisjoint(manifest)
    assert RUNTIME_ONLY_KEYS.isdisjoint(manifest["metadata"])
    assert all(RUNTIME_ONLY_KEYS.isdisjoint(node) for node in manifest["nodes"])


def test_manifest_exposes_ui_facing_nodes_with_params_schema() -> None:
    manifest = load_manifest()

    node_map = {node["id"]: node for node in manifest["nodes"]}

    assert node_map[TEXT_TO_IMAGE_NODE_ID]["params_schema"]
    assert node_map[IMAGE_TO_IMAGE_NODE_ID]["params_schema"]
    assert any(param["id"] == "prompt" for param in node_map[TEXT_TO_IMAGE_NODE_ID]["params_schema"])
    assert any(param["id"] == "strength" for param in node_map[IMAGE_TO_IMAGE_NODE_ID]["params_schema"])


def test_image_to_image_declares_named_inputs_without_visible_path_params() -> None:
    manifest = load_manifest()
    image_node = {node["id"]: node for node in manifest["nodes"]}[IMAGE_TO_IMAGE_NODE_ID]

    assert image_node["inputs"] == [
        {"name": "front", "label": "Primary image", "type": "image", "required": True},
        {"name": "left", "label": "Image 2", "type": "image", "required": False},
        {"name": "back", "label": "Image 3", "type": "image", "required": False},
        {"name": "right", "label": "Image 4", "type": "image", "required": False},
    ]
    visible_param_ids = {param["id"] for param in image_node["params_schema"]}
    assert {"front_image_path", "left_image_path", "back_image_path", "right_image_path"}.isdisjoint(visible_param_ids)
