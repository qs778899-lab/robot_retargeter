"""Convert mapped BVH FK results to the project semantic skeleton."""

from __future__ import annotations

from .base import BvhMotion, HumanMapping, HumanSemanticMotion, SourceMotion
from .mappings import resolve_source_joint

import numpy as np

SKELETON_BODY_NAMES = [
    "hips",
    "left_up_leg",
    "left_leg",
    "left_foot",
    "left_toe",
    "right_up_leg",
    "right_leg",
    "right_foot",
    "right_toe",
    "spine1",
    "spine2",
    "chest",
    "neck",
    "head",
    "left_shoulder",
    "left_arm",
    "left_fore_arm",
    "left_hand",
    "right_shoulder",
    "right_arm",
    "right_fore_arm",
    "right_hand",
]

DERIVED_BODY_CENTERS = {
    "hips_mean": (("left_up_leg", "right_up_leg"),),
    "shoulder_mean": (
        ("left_shoulder", "right_shoulder"),
        ("left_arm", "right_arm"),
    ),
}

REPLAY_BODY_NAMES = SKELETON_BODY_NAMES + list(DERIVED_BODY_CENTERS.keys())


def motion_to_semantic(
    motion: BvhMotion,
    mapping: HumanMapping,
    source: SourceMotion | None = None,
) -> HumanSemanticMotion:
    source = source or SourceMotion(
        motion_bvh=motion.path,
        output_stem=motion.path.stem,
        source_format="bvh",
        display_name=motion.path.name,
    )
    src_indices = {name: idx for idx, name in enumerate(motion.joint_names)}
    semantic_indices = {name: idx for idx, name in enumerate(REPLAY_BODY_NAMES)}
    positions = np.zeros((motion.positions.shape[0], len(REPLAY_BODY_NAMES), 3), dtype=np.float32)
    quaternions = np.zeros((motion.positions.shape[0], len(REPLAY_BODY_NAMES), 4), dtype=np.float32)
    filled: set[str] = set()
    warnings: list[str] = []

    quaternions[:, :, 0] = 1.0
    for source_name in motion.joint_names:
        target_name = resolve_source_joint(mapping, source_name)
        if target_name is None or target_name not in semantic_indices:
            continue
        target_idx = semantic_indices[target_name]
        source_idx = src_indices[source_name]
        positions[:, target_idx, :] = motion.positions[:, source_idx, :]
        quaternions[:, target_idx, :] = motion.quaternions[:, source_idx, :]
        filled.add(target_name)

    _derive_center(
        "hips_mean",
        DERIVED_BODY_CENTERS["hips_mean"],
        positions,
        quaternions,
        filled,
        orientation_source="hips",
    )
    _derive_center(
        "shoulder_mean",
        DERIVED_BODY_CENTERS["shoulder_mean"],
        positions,
        quaternions,
        filled,
    )
    _derive_spine_points(positions, quaternions, filled, warnings)
    _derive_head(positions, quaternions, filled, warnings)
    _derive_toe("left_toe", "left_foot", positions, quaternions, filled, warnings)
    _derive_toe("right_toe", "right_foot", positions, quaternions, filled, warnings)

    return HumanSemanticMotion(
        source=source,
        body_names=list(REPLAY_BODY_NAMES),
        positions=positions,
        quaternions=_normalize_quaternions(quaternions),
        fps=motion.fps,
        warnings=tuple(warnings),
    )


def _derive_center(
    target: str,
    source_options: tuple[tuple[str, str], ...],
    positions: np.ndarray,
    quaternions: np.ndarray,
    filled: set[str],
    orientation_source: str | None = None,
) -> None:
    if target in filled:
        return
    for sources in source_options:
        if sources[0] not in filled or sources[1] not in filled:
            continue
        target_idx = REPLAY_BODY_NAMES.index(target)
        left_idx = REPLAY_BODY_NAMES.index(sources[0])
        right_idx = REPLAY_BODY_NAMES.index(sources[1])
        positions[:, target_idx, :] = 0.5 * (positions[:, left_idx, :] + positions[:, right_idx, :])
        if orientation_source is not None and orientation_source in filled:
            source_idx = REPLAY_BODY_NAMES.index(orientation_source)
            quaternions[:, target_idx, :] = quaternions[:, source_idx, :]
        else:
            quaternions[:, target_idx, :] = _average_quaternions(
                quaternions[:, left_idx, :], quaternions[:, right_idx, :]
            )
        filled.add(target)
        return


def _derive_spine_points(
    positions: np.ndarray,
    quaternions: np.ndarray,
    filled: set[str],
    warnings: list[str],
) -> None:
    if "hips" not in filled or "chest" not in filled:
        return
    hips_idx = REPLAY_BODY_NAMES.index("hips")
    chest_idx = REPLAY_BODY_NAMES.index("chest")
    for name, weight in (("spine1", 1.0 / 3.0), ("spine2", 2.0 / 3.0)):
        if name in filled:
            continue
        idx = REPLAY_BODY_NAMES.index(name)
        positions[:, idx, :] = (1.0 - weight) * positions[:, hips_idx, :] + weight * positions[
            :, chest_idx, :
        ]
        quaternions[:, idx, :] = quaternions[:, chest_idx, :]
        filled.add(name)
        warnings.append(f"{name} missing; interpolated between hips and chest")


def _derive_head(
    positions: np.ndarray,
    quaternions: np.ndarray,
    filled: set[str],
    warnings: list[str],
) -> None:
    if "head" in filled or "neck" not in filled:
        return
    head_idx = REPLAY_BODY_NAMES.index("head")
    neck_idx = REPLAY_BODY_NAMES.index("neck")
    if "chest" in filled:
        chest_idx = REPLAY_BODY_NAMES.index("chest")
        positions[:, head_idx, :] = positions[:, neck_idx, :] + (
            positions[:, neck_idx, :] - positions[:, chest_idx, :]
        )
    else:
        positions[:, head_idx, :] = positions[:, neck_idx, :]
    quaternions[:, head_idx, :] = quaternions[:, neck_idx, :]
    filled.add("head")
    warnings.append("head missing; extrapolated from neck/chest")


def _derive_toe(
    toe_name: str,
    foot_name: str,
    positions: np.ndarray,
    quaternions: np.ndarray,
    filled: set[str],
    warnings: list[str],
) -> None:
    if toe_name in filled or foot_name not in filled:
        return
    toe_idx = REPLAY_BODY_NAMES.index(toe_name)
    foot_idx = REPLAY_BODY_NAMES.index(foot_name)
    positions[:, toe_idx, :] = positions[:, foot_idx, :]
    quaternions[:, toe_idx, :] = quaternions[:, foot_idx, :]
    filled.add(toe_name)
    warnings.append(f"{toe_name} missing; copied from {foot_name}")


def _average_quaternions(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    aligned_q2 = np.where(np.sum(q1 * q2, axis=-1, keepdims=True) < 0.0, -q2, q2)
    return _normalize_quaternions(q1 + aligned_q2)


def _normalize_quaternions(quaternions: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(quaternions, axis=-1, keepdims=True)
    return quaternions / np.clip(norms, 1e-8, None)
