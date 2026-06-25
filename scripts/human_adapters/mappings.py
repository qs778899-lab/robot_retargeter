"""Mapping schema helpers for human BVH adapters."""

from __future__ import annotations

import json
from pathlib import Path

from .base import HumanMapping


DEFAULT_REQUIRED_SEMANTIC_JOINTS = (
    "hips",
    "chest",
    "neck",
    "left_up_leg",
    "left_leg",
    "left_foot",
    "right_up_leg",
    "right_leg",
    "right_foot",
    "left_arm",
    "left_fore_arm",
    "left_hand",
    "right_arm",
    "right_fore_arm",
    "right_hand",
)


def load_human_mapping(path: Path | str) -> HumanMapping:
    mapping_path = Path(path)
    with mapping_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    raw_mapping = payload.get("mapping")
    if not isinstance(raw_mapping, dict) or not raw_mapping:
        raise ValueError(f"Missing non-empty 'mapping' object in {mapping_path}")

    aliases = payload.get("aliases", {})
    if aliases is None:
        aliases = {}
    if not isinstance(aliases, dict):
        raise ValueError(f"'aliases' must be an object in {mapping_path}")

    required = payload.get("required", DEFAULT_REQUIRED_SEMANTIC_JOINTS)
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise ValueError(f"'required' must be a string list in {mapping_path}")

    mapping = {str(source): str(target) for source, target in raw_mapping.items()}
    alias_mapping = {str(source): str(target) for source, target in aliases.items()}
    human_mapping = HumanMapping(
        path=mapping_path,
        description=str(payload.get("description", "")),
        mapping=mapping,
        aliases=alias_mapping,
        required=tuple(required),
    )
    validate_human_mapping(human_mapping)
    return human_mapping


def validate_human_mapping(mapping: HumanMapping) -> None:
    targets = set(mapping.mapping.values()) | set(mapping.aliases.values())
    missing = [name for name in mapping.required if name not in targets]
    if missing:
        raise ValueError(
            f"{mapping.path} missing required semantic targets: {', '.join(missing)}"
        )


def resolve_source_joint(mapping: HumanMapping, source_joint: str) -> str | None:
    if source_joint in mapping.mapping:
        return mapping.mapping[source_joint]
    return mapping.aliases.get(source_joint)
