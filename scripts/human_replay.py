#!/usr/bin/env python3
"""Convert human BVH motions to retarget-ready keypoints pkl files."""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from human_adapters import (
    MAYA_TO_MUJOCO,
    axis_transform_to_mujoco,
    compute_axis_debug_info,
    load_bvh,
    load_human_mapping,
    motion_to_semantic,
    pns,
    transform_motion,
    v3,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKELETON_CONFIG = PROJECT_ROOT / "config" / "skeleton" / "skeleton.yaml"

BODY_CHILDREN = {
    "left_up_leg": "left_leg",
    "left_leg": "left_foot",
    "left_foot": "left_toe",
    "right_up_leg": "right_leg",
    "right_leg": "right_foot",
    "right_foot": "right_toe",
    "spine1": "spine2",
    "spine2": "chest",
    "chest": "neck",
    "neck": "head",
    "left_shoulder": "left_arm",
    "left_arm": "left_fore_arm",
    "left_fore_arm": "left_hand",
    "right_shoulder": "right_arm",
    "right_arm": "right_fore_arm",
    "right_fore_arm": "right_hand",
}

BODY_LOCAL_DIRECTIONS_MUJOCO = {
    "left_up_leg": np.array([0.0, 0.0, -1.0], dtype=np.float32),
    "left_leg": np.array([0.0, 0.0, -1.0], dtype=np.float32),
    "left_foot": np.array([1.0, 0.0, -0.25], dtype=np.float32),
    "right_up_leg": np.array([0.0, 0.0, -1.0], dtype=np.float32),
    "right_leg": np.array([0.0, 0.0, -1.0], dtype=np.float32),
    "right_foot": np.array([1.0, 0.0, -0.25], dtype=np.float32),
    "spine1": np.array([0.0, 0.0, 1.0], dtype=np.float32),
    "spine2": np.array([0.0, 0.0, 1.0], dtype=np.float32),
    "chest": np.array([0.0, 0.0, 1.0], dtype=np.float32),
    "neck": np.array([0.0, 0.0, 1.0], dtype=np.float32),
    "left_shoulder": np.array([0.0, 1.0, 0.0], dtype=np.float32),
    "left_arm": np.array([0.0, 1.0, 0.0], dtype=np.float32),
    "left_fore_arm": np.array([0.0, 1.0, 0.0], dtype=np.float32),
    "right_shoulder": np.array([0.0, -1.0, 0.0], dtype=np.float32),
    "right_arm": np.array([0.0, -1.0, 0.0], dtype=np.float32),
    "right_fore_arm": np.array([0.0, -1.0, 0.0], dtype=np.float32),
}

BVH_IK_ORIENTATION_COST_SCALES = {
    "left_shoulder": 0.0,
    "left_arm": 0.0,
    "left_fore_arm": 0.0,
    "right_shoulder": 0.0,
    "right_arm": 0.0,
    "right_fore_arm": 0.0,
}

FOOT_ORIENTATION_KEYPOINTS_BY_FORMAT = {
    "pns": {
        "left_calf": "left_foot",
        "right_calf": "right_foot",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert PNS/v3 human BVH files to robot_retargeter keypoints pkl."
    )
    parser.add_argument("--format", choices=["pns", "v3"], required=True)
    parser.add_argument("--task", default=None)
    parser.add_argument("--input-bvh", type=Path, default=None)
    parser.add_argument("--input-dir", type=Path, default=None)
    parser.add_argument("--input-root", type=Path, default=None)
    parser.add_argument("--robot-config", type=Path, required=True)
    parser.add_argument("--skeleton-config", type=Path, default=DEFAULT_SKELETON_CONFIG)
    parser.add_argument("--mapping", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--facing-direction", choices=["auto", "Maya", "Mujoco"], default="auto")
    parser.add_argument(
        "--unit-scale",
        default="auto",
        help="Unit scale applied before axis conversion. Use 'auto' or a float.",
    )
    parser.add_argument("--strip-dead-frames", action="store_true", help="Reserved for phase 4 CLI compatibility.")
    parser.add_argument("--no-viewer", action="store_true", help="Accepted for parity with replay scripts.")
    return parser.parse_args()


def resolve_mapping_path(source_format: str, explicit_mapping: Path | None) -> Path:
    if explicit_mapping is not None:
        return explicit_mapping
    return PROJECT_ROOT / "config" / "human_mappings" / f"{source_format}.json"


def resolve_sources(args: argparse.Namespace):
    input_root = args.input_root
    if input_root is not None and not input_root.is_absolute():
        input_root = PROJECT_ROOT / input_root

    adapter = pns if args.format == "pns" else v3
    kwargs = {
        "task": args.task,
        "input_bvh": args.input_bvh,
        "input_dir": args.input_dir,
    }
    if input_root is not None:
        kwargs["input_root"] = input_root
    return adapter.discover(**kwargs)


def resolve_unit_scale(value: str, inferred_scale: float) -> float:
    if value == "auto":
        return float(inferred_scale)
    return float(value)


def resolve_project_path(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return PROJECT_ROOT / expanded


def load_link_pairs(config_path: Path, section_name: str) -> dict[str, tuple[str, str]]:
    links: dict[str, tuple[str, str]] = {}
    in_section = False
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not in_section:
            if line.strip() == f"{section_name}:":
                in_section = True
            continue
        if not raw_line[:1].isspace():
            break

        stripped = line.strip()
        link_name, separator, body_spec = stripped.partition(":")
        if not separator:
            raise ValueError(f"Invalid {section_name} entry: {raw_line}")
        body_spec = body_spec.strip()
        if not (body_spec.startswith("[") and body_spec.endswith("]")):
            raise ValueError(f"Invalid {section_name} body pair: {raw_line}")
        body_names = [item.strip() for item in body_spec[1:-1].split(",")]
        if len(body_names) != 2 or not all(body_names):
            raise ValueError(f"{section_name}.{link_name} must contain two body names")
        links[link_name.strip()] = (body_names[0], body_names[1])
    if not links:
        raise ValueError(f"Missing non-empty {section_name} in {config_path}")
    return links


def load_key_frame_config(config_path: Path) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    offset_map: dict[str, np.ndarray] = {}
    axis_map: dict[str, np.ndarray] = {}
    in_section = False
    current_body: str | None = None
    current_offset: np.ndarray | None = None
    current_axes: dict[str, np.ndarray] = {}
    in_axis_subsection = False

    def flush_current() -> None:
        nonlocal current_body, current_offset, current_axes, in_axis_subsection
        if current_body is None:
            return
        if current_offset is None:
            current_offset = np.zeros(3, dtype=np.float32)
        if set(current_axes) != {"x", "y", "z"}:
            current_axes = {
                "x": np.array([1.0, 0.0, 0.0], dtype=np.float32),
                "y": np.array([0.0, 1.0, 0.0], dtype=np.float32),
                "z": np.array([0.0, 0.0, 1.0], dtype=np.float32),
            }
        offset_map[current_body] = current_offset
        axis_map[current_body] = np.column_stack(
            [current_axes["x"], current_axes["y"], current_axes["z"]]
        ).astype(np.float32)
        current_body = None
        current_offset = None
        current_axes = {}
        in_axis_subsection = False

    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not in_section:
            if line.strip() == "key_frame_config:":
                in_section = True
            continue
        if not raw_line[:1].isspace():
            break

        indent = len(raw_line) - len(raw_line.lstrip())
        stripped = line.strip()
        if indent <= 2 and ":" in stripped:
            flush_current()
            name, _, _rest = stripped.partition(":")
            current_body = name.strip()
            continue
        if current_body is None:
            continue
        if indent <= 4 and stripped.startswith("offset_deg_xyz"):
            _key, _, value = stripped.partition(":")
            current_offset = _parse_float_list(value, expected_len=3)
            continue
        if indent <= 4 and stripped.startswith("axis_map_cols"):
            in_axis_subsection = True
            continue
        if in_axis_subsection and indent >= 6 and ":" in stripped:
            axis_name, _, value = stripped.partition(":")
            axis_name = axis_name.strip().lower()
            if axis_name in {"x", "y", "z"}:
                current_axes[axis_name] = _parse_float_list(value, expected_len=3)

    flush_current()
    return offset_map, axis_map


def _parse_float_list(value: str, expected_len: int) -> np.ndarray:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        raise ValueError(f"Invalid list value: {value}")
    parts = [item.strip() for item in value[1:-1].split(",") if item.strip()]
    if len(parts) != expected_len:
        raise ValueError(f"Expected {expected_len} values, got: {value}")
    return np.asarray([float(item) for item in parts], dtype=np.float32)


def load_path_field(config_path: Path, field_name: str) -> Path:
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        key, separator, value = line.partition(":")
        if separator and key.strip() == field_name:
            parsed = value.strip()
            if parsed[:1] in {"'", '"'} and parsed[-1:] == parsed[:1]:
                parsed = parsed[1:-1]
            return Path(parsed)
    raise ValueError(f"Missing {field_name} in {config_path}")


def compute_robot_link_lengths_and_body_poses(
    robot_config: Path,
) -> tuple[dict[str, float], dict[str, np.ndarray], dict[str, np.ndarray]]:
    import mujoco

    robot_xml = resolve_project_path(load_path_field(robot_config, "robot_xml_path"))
    robot_links = load_link_pairs(robot_config, "robot_links")
    model = mujoco.MjModel.from_xml_path(str(robot_xml))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    lengths: dict[str, float] = {}
    body_positions: dict[str, np.ndarray] = {}
    body_quaternions: dict[str, np.ndarray] = {}
    for link_name, (parent_body, child_body) in robot_links.items():
        parent_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, parent_body)
        child_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, child_body)
        if parent_id < 0 or child_id < 0:
            raise ValueError(f"Missing robot body for {link_name}: {parent_body}, {child_body}")
        lengths[link_name] = float(np.linalg.norm(data.xpos[child_id] - data.xpos[parent_id]))
        body_positions[parent_body] = data.xpos[parent_id].copy()
        body_positions[child_body] = data.xpos[child_id].copy()
        body_quaternions[parent_body] = data.xquat[parent_id].copy()
        body_quaternions[child_body] = data.xquat[child_id].copy()
    return lengths, body_positions, body_quaternions


def normalize_vectors(vectors: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    return vectors / np.clip(np.linalg.norm(vectors, axis=-1, keepdims=True), eps, None)


def batch_rotation_between_vectors_wxyz(
    v_from: np.ndarray,
    v_to: np.ndarray,
    eps: float = 1e-8,
) -> np.ndarray:
    from_u = normalize_vectors(np.asarray(v_from, dtype=np.float64), eps=eps)
    to_u = normalize_vectors(np.asarray(v_to, dtype=np.float64), eps=eps)
    dot = np.clip(np.sum(from_u * to_u, axis=-1, keepdims=True), -1.0, 1.0)
    cross = np.cross(from_u, to_u)
    quat = np.concatenate([1.0 + dot, cross], axis=-1)

    antiparallel = dot[:, 0] < (-1.0 + 1e-7)
    if np.any(antiparallel):
        fallback = np.cross(from_u[antiparallel], np.array([1.0, 0.0, 0.0], dtype=np.float64))
        fallback_norm = np.linalg.norm(fallback, axis=-1, keepdims=True)
        fallback = np.where(
            fallback_norm > eps,
            fallback,
            np.cross(from_u[antiparallel], np.array([0.0, 1.0, 0.0], dtype=np.float64)),
        )
        fallback = normalize_vectors(fallback, eps=eps)
        quat[antiparallel] = np.concatenate(
            [np.zeros((fallback.shape[0], 1), dtype=np.float64), fallback],
            axis=-1,
        )

    return normalize_vectors(quat, eps=eps).astype(np.float32)


def multiply_quaternions_wxyz(q_left: np.ndarray, q_right: np.ndarray) -> np.ndarray:
    left = np.asarray(q_left, dtype=np.float64)
    right = np.asarray(q_right, dtype=np.float64)
    w1, x1, y1, z1 = [left[..., i] for i in range(4)]
    w2, x2, y2, z2 = [right[..., i] for i in range(4)]
    result = np.stack(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ],
        axis=-1,
    )
    return normalize_vectors(result).astype(np.float32)


def quat_from_vectors_wxyz(v_from: np.ndarray, v_to: np.ndarray) -> np.ndarray:
    from_u = normalize_vectors(np.asarray(v_from, dtype=np.float64))
    to_u = normalize_vectors(np.asarray(v_to, dtype=np.float64))
    rotation, _rssd = Rotation.align_vectors(to_u, from_u)
    quat_xyzw = rotation.as_quat()
    return quat_xyzw[[3, 0, 1, 2]].astype(np.float32)


def align_semantic_link_quaternions(
    positions: np.ndarray,
    body_names: list[str],
    fallback_quaternions: np.ndarray,
) -> np.ndarray:
    indices = {name: idx for idx, name in enumerate(body_names)}
    aligned = fallback_quaternions.copy()
    identity = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)

    for body_name, child_name in BODY_CHILDREN.items():
        if body_name not in indices or child_name not in indices:
            continue
        local_dir = BODY_LOCAL_DIRECTIONS_MUJOCO.get(body_name)
        if local_dir is None:
            continue
        local_dir = normalize_vectors(local_dir.reshape(1, 3))[0]
        body_idx = indices[body_name]
        child_idx = indices[child_name]
        for frame_idx in range(positions.shape[0]):
            bone_vec = positions[frame_idx, child_idx] - positions[frame_idx, body_idx]
            if np.linalg.norm(bone_vec) < 1e-8:
                aligned[frame_idx, body_idx] = identity
                continue
            aligned[frame_idx, body_idx] = quat_from_vectors_wxyz(local_dir, bone_vec)

    return aligned


def apply_axis_map_and_local_euler_offset_wxyz(
    quaternions_wxyz: np.ndarray,
    axis_map: np.ndarray,
    euler_xyz_degrees: np.ndarray,
) -> np.ndarray:
    base_mats = Rotation.from_quat(quaternions_wxyz[:, [1, 2, 3, 0]]).as_matrix()
    if axis_map.shape != (3, 3):
        raise ValueError(f"axis_map shape must be (3, 3), got {axis_map.shape}")
    euler_rad = np.radians(euler_xyz_degrees.astype(np.float64))
    offset_mat = Rotation.from_euler("xyz", euler_rad).as_matrix()
    adjusted_mats = np.einsum(
        "nij,jk->nik",
        base_mats,
        axis_map.astype(np.float64) @ offset_mat,
    )
    adjusted_xyzw = Rotation.from_matrix(adjusted_mats).as_quat()
    return adjusted_xyzw[:, [3, 0, 1, 2]].astype(np.float32)


def build_robot_keypoints(
    *,
    semantic_positions: np.ndarray,
    semantic_quaternions: np.ndarray,
    semantic_names: list[str],
    robot_links: dict[str, tuple[str, str]],
    robot_link_lengths: dict[str, float],
    robot_body_positions: dict[str, np.ndarray],
    robot_body_quaternions: dict[str, np.ndarray],
    skeleton_links: dict[str, tuple[str, str]],
    key_frame_offsets: dict[str, np.ndarray],
    key_frame_axis_maps: dict[str, np.ndarray],
) -> tuple[list[str], np.ndarray, np.ndarray]:
    semantic_idx = {name: idx for idx, name in enumerate(semantic_names)}
    frame_count = semantic_positions.shape[0]
    keypoint_names = ["hips_mean", *list(robot_links.keys())]
    keypoints = np.zeros((frame_count, len(keypoint_names), 3), dtype=np.float32)
    quaternions = np.zeros((frame_count, len(keypoint_names), 4), dtype=np.float32)
    retargeted: dict[str, np.ndarray] = {}

    root_idx = semantic_idx["hips_mean"]
    keypoints[:, 0, :] = semantic_positions[:, root_idx, :]
    quaternions[:, 0, :] = apply_axis_map_and_local_euler_offset_wxyz(
        semantic_quaternions[:, root_idx, :],
        key_frame_axis_maps.get("hips_mean", np.eye(3, dtype=np.float32)),
        key_frame_offsets.get("hips_mean", np.zeros(3, dtype=np.float32)),
    )
    retargeted["hips_mean"] = keypoints[:, 0, :]

    for output_idx, link_name in enumerate(robot_links, start=1):
        if link_name not in skeleton_links:
            raise ValueError(f"Missing skeleton link for robot link: {link_name}")
        parent_name, child_name = skeleton_links[link_name]
        if parent_name not in semantic_idx or child_name not in semantic_idx:
            raise ValueError(f"Missing semantic bodies for {link_name}: {parent_name}, {child_name}")

        parent_positions = retargeted.get(parent_name, semantic_positions[:, semantic_idx[parent_name], :])
        source_vec = (
            semantic_positions[:, semantic_idx[child_name], :]
            - semantic_positions[:, semantic_idx[parent_name], :]
        )
        source_len = np.linalg.norm(source_vec, axis=-1)
        valid_len = source_len[source_len > 1e-8]
        scale = 1.0
        if valid_len.size:
            scale = robot_link_lengths[link_name] / float(np.mean(valid_len))
        child_positions = parent_positions + scale * source_vec
        keypoints[:, output_idx, :] = child_positions
        robot_parent_body, robot_child_body = robot_links[link_name]
        rest_vec = robot_body_positions[robot_child_body] - robot_body_positions[robot_parent_body]
        target_vec = child_positions - parent_positions
        correction = batch_rotation_between_vectors_wxyz(
            np.broadcast_to(rest_vec, target_vec.shape),
            target_vec,
        )
        rest_child_quat = np.broadcast_to(
            robot_body_quaternions[robot_child_body],
            correction.shape,
        )
        quaternions[:, output_idx, :] = multiply_quaternions_wxyz(correction, rest_child_quat)
        retargeted[child_name] = child_positions

    return keypoint_names, keypoints, quaternions


def align_keypoints_to_robot_ground(
    *,
    keypoint_names: list[str],
    keypoints: np.ndarray,
    robot_links: dict[str, tuple[str, str]],
    robot_body_positions: dict[str, np.ndarray],
) -> tuple[np.ndarray, float, float, float, tuple[str, ...]]:
    support_links = tuple(
        link_name
        for link_name in ("left_calf", "right_calf", "left_foot", "right_foot")
        if link_name in keypoint_names and link_name in robot_links
    )
    if not support_links:
        return keypoints, 0.0, float("nan"), float("nan"), ()

    keypoint_idx = {name: idx for idx, name in enumerate(keypoint_names)}
    observed_min = float(
        np.min([np.min(keypoints[:, keypoint_idx[name], 2]) for name in support_links])
    )
    desired_values = [
        robot_body_positions[robot_links[name][1]][2]
        for name in support_links
        if robot_links[name][1] in robot_body_positions
    ]
    if not desired_values:
        return keypoints, 0.0, observed_min, float("nan"), support_links
    desired_min = float(np.min(desired_values))
    z_shift = desired_min - observed_min
    aligned = keypoints.copy()
    aligned[:, :, 2] += z_shift
    return aligned, z_shift, observed_min, desired_min, support_links


def apply_format_foot_orientation_overrides(
    *,
    source_format: str,
    keypoint_names: list[str],
    keypoint_quaternions: np.ndarray,
    semantic_quaternions: np.ndarray,
    semantic_names: list[str],
    key_frame_offsets: dict[str, np.ndarray],
    key_frame_axis_maps: dict[str, np.ndarray],
) -> np.ndarray:
    overrides = FOOT_ORIENTATION_KEYPOINTS_BY_FORMAT.get(source_format)
    if not overrides:
        return keypoint_quaternions

    keypoint_idx = {name: idx for idx, name in enumerate(keypoint_names)}
    semantic_idx = {name: idx for idx, name in enumerate(semantic_names)}
    adjusted = keypoint_quaternions.copy()
    for keypoint_name, semantic_foot_name in overrides.items():
        if keypoint_name not in keypoint_idx or semantic_foot_name not in semantic_idx:
            continue
        adjusted[:, keypoint_idx[keypoint_name], :] = apply_axis_map_and_local_euler_offset_wxyz(
            semantic_quaternions[:, semantic_idx[semantic_foot_name], :],
            key_frame_axis_maps.get(semantic_foot_name, np.eye(3, dtype=np.float32)),
            key_frame_offsets.get(semantic_foot_name, np.zeros(3, dtype=np.float32)),
        )
    return adjusted


def save_keypoints_pkl(
    output_path: Path,
    *,
    keypoint_names: list[str],
    positions: np.ndarray,
    quaternions: np.ndarray,
    fps: float,
    orientation_cost_scales: dict[str, float] | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "keypoint_names": keypoint_names,
        "positions": positions.astype(np.float32),
        "quaternions": quaternions.astype(np.float32),
        "fps": float(fps),
        "contact_names": [],
        "contact_states": np.zeros((positions.shape[0], 0), dtype=np.bool_),
    }
    if orientation_cost_scales:
        payload["ik_orientation_cost_scales"] = {
            name: float(scale) for name, scale in orientation_cost_scales.items()
        }
    with output_path.open("wb") as f:
        pickle.dump(payload, f)
    print(f"Saved keypoints to: {output_path}")


def convert_one(args: argparse.Namespace, source, mapping) -> Path:
    raw_motion = load_bvh(source.motion_bvh)
    raw_debug = compute_axis_debug_info(raw_motion)
    unit_scale = resolve_unit_scale(args.unit_scale, raw_debug.unit_scale)

    if args.facing_direction == "auto":
        axis_transform = axis_transform_to_mujoco(raw_debug)
    elif args.facing_direction == "Maya":
        axis_transform = MAYA_TO_MUJOCO
    else:
        axis_transform = np.eye(3)

    motion = transform_motion(raw_motion, unit_scale=unit_scale, axis_transform=axis_transform)

    semantic = motion_to_semantic(motion, mapping, source)
    semantic_quaternions = align_semantic_link_quaternions(
        semantic.positions,
        semantic.body_names,
        semantic.quaternions,
    )

    robot_config = resolve_project_path(args.robot_config)
    skeleton_config = resolve_project_path(args.skeleton_config)
    robot_links = load_link_pairs(robot_config, "robot_links")
    skeleton_links = load_link_pairs(skeleton_config, "skeleton_links")
    key_frame_offsets, key_frame_axis_maps = load_key_frame_config(robot_config)
    (
        robot_link_lengths,
        robot_body_positions,
        robot_body_quaternions,
    ) = compute_robot_link_lengths_and_body_poses(robot_config)
    keypoint_names, keypoints, quaternions = build_robot_keypoints(
        semantic_positions=semantic.positions,
        semantic_quaternions=semantic_quaternions,
        semantic_names=semantic.body_names,
        robot_links=robot_links,
        robot_link_lengths=robot_link_lengths,
        robot_body_positions=robot_body_positions,
        robot_body_quaternions=robot_body_quaternions,
        skeleton_links=skeleton_links,
        key_frame_offsets=key_frame_offsets,
        key_frame_axis_maps=key_frame_axis_maps,
    )
    keypoints, z_shift, observed_ground_z, target_ground_z, ground_links = align_keypoints_to_robot_ground(
        keypoint_names=keypoint_names,
        keypoints=keypoints,
        robot_links=robot_links,
        robot_body_positions=robot_body_positions,
    )
    quaternions = apply_format_foot_orientation_overrides(
        source_format=args.format,
        keypoint_names=keypoint_names,
        keypoint_quaternions=quaternions,
        semantic_quaternions=semantic_quaternions,
        semantic_names=semantic.body_names,
        key_frame_offsets=key_frame_offsets,
        key_frame_axis_maps=key_frame_axis_maps,
    )

    output_dir = args.output_dir
    if output_dir is None:
        output_dir = PROJECT_ROOT / "output_data" / "keypoints" / robot_config.stem
    else:
        output_dir = resolve_project_path(output_dir)
    output_path = output_dir / f"{source.output_stem}_keypoints.pkl"

    save_keypoints_pkl(
        output_path=output_path,
        keypoint_names=keypoint_names,
        positions=keypoints,
        quaternions=quaternions,
        fps=semantic.fps,
        orientation_cost_scales=BVH_IK_ORIENTATION_COST_SCALES,
    )

    print(
        "[human-bvh-debug] "
        f"source={source.display_name} raw_height={raw_debug.raw_height:.6g} "
        f"unit_scale={unit_scale:.6g} unit_reason={raw_debug.unit_reason!r} "
        f"up_axis={raw_debug.up_axis} lateral_axis={raw_debug.lateral_axis} "
        f"forward_axis={raw_debug.forward_axis} root_xyz_range={raw_debug.root_xyz_range} "
        f"axis_transform={axis_transform.tolist()} "
        f"ground_links={ground_links} observed_ground_z={observed_ground_z:.6g} "
        f"target_ground_z={target_ground_z:.6g} z_shift={z_shift:.6g} "
        f"head_minus_feet_mean={raw_debug.head_minus_feet_mean} "
        f"left_right_hip_delta_mean={raw_debug.left_right_hip_delta_mean} "
        f"foot_to_toe_delta_mean={raw_debug.foot_to_toe_delta_mean}"
    )
    for warning in semantic.warnings:
        print(f"[human-bvh-warning] {source.display_name}: {warning}")
    return output_path


def main() -> int:
    args = parse_args()
    mapping = load_human_mapping(resolve_mapping_path(args.format, args.mapping))
    sources = resolve_sources(args)
    if not sources:
        print("[DONE] no BVH sources found")
        return 0

    for source in sources:
        output_path = convert_one(args, source, mapping)
        print(f"[OK] {source.motion_bvh} -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
