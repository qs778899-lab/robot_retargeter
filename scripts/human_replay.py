#!/usr/bin/env python3
"""Convert human BVH motions to retarget-ready keypoints pkl files."""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np

from human_adapters import (
    MAYA_TO_MUJOCO,
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
    parser.add_argument("--facing-direction", choices=["Maya", "Mujoco"], default="Maya")
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


def compute_robot_link_lengths(robot_config: Path) -> dict[str, float]:
    import mujoco

    robot_xml = resolve_project_path(load_path_field(robot_config, "robot_xml_path"))
    robot_links = load_link_pairs(robot_config, "robot_links")
    model = mujoco.MjModel.from_xml_path(str(robot_xml))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    lengths: dict[str, float] = {}
    for link_name, (parent_body, child_body) in robot_links.items():
        parent_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, parent_body)
        child_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, child_body)
        if parent_id < 0 or child_id < 0:
            raise ValueError(f"Missing robot body for {link_name}: {parent_body}, {child_body}")
        lengths[link_name] = float(np.linalg.norm(data.xpos[child_id] - data.xpos[parent_id]))
    return lengths


def build_robot_keypoints(
    *,
    semantic_positions: np.ndarray,
    semantic_quaternions: np.ndarray,
    semantic_names: list[str],
    robot_links: dict[str, tuple[str, str]],
    robot_link_lengths: dict[str, float],
    skeleton_links: dict[str, tuple[str, str]],
) -> tuple[list[str], np.ndarray, np.ndarray]:
    semantic_idx = {name: idx for idx, name in enumerate(semantic_names)}
    frame_count = semantic_positions.shape[0]
    keypoint_names = ["hips_mean", *list(robot_links.keys())]
    keypoints = np.zeros((frame_count, len(keypoint_names), 3), dtype=np.float32)
    quaternions = np.zeros((frame_count, len(keypoint_names), 4), dtype=np.float32)
    retargeted: dict[str, np.ndarray] = {}

    root_idx = semantic_idx["hips_mean"]
    keypoints[:, 0, :] = semantic_positions[:, root_idx, :]
    quaternions[:, 0, :] = semantic_quaternions[:, root_idx, :]
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
        quaternions[:, output_idx, :] = semantic_quaternions[:, semantic_idx[child_name], :]
        retargeted[child_name] = child_positions

    return keypoint_names, keypoints, quaternions


def save_keypoints_pkl(
    output_path: Path,
    *,
    keypoint_names: list[str],
    positions: np.ndarray,
    quaternions: np.ndarray,
    fps: float,
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
    with output_path.open("wb") as f:
        pickle.dump(payload, f)
    print(f"Saved keypoints to: {output_path}")


def convert_one(args: argparse.Namespace, source, mapping) -> Path:
    raw_motion = load_bvh(source.motion_bvh)
    raw_debug = compute_axis_debug_info(raw_motion)
    unit_scale = resolve_unit_scale(args.unit_scale, raw_debug.unit_scale)

    if args.facing_direction == "Maya":
        motion = transform_motion(raw_motion, unit_scale=unit_scale, axis_transform=MAYA_TO_MUJOCO)
    else:
        motion = transform_motion(raw_motion, unit_scale=unit_scale, axis_transform=np.eye(3))

    semantic = motion_to_semantic(motion, mapping, source)

    robot_config = resolve_project_path(args.robot_config)
    skeleton_config = resolve_project_path(args.skeleton_config)
    robot_links = load_link_pairs(robot_config, "robot_links")
    skeleton_links = load_link_pairs(skeleton_config, "skeleton_links")
    robot_link_lengths = compute_robot_link_lengths(robot_config)
    keypoint_names, keypoints, quaternions = build_robot_keypoints(
        semantic_positions=semantic.positions,
        semantic_quaternions=semantic.quaternions,
        semantic_names=semantic.body_names,
        robot_links=robot_links,
        robot_link_lengths=robot_link_lengths,
        skeleton_links=skeleton_links,
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
    )

    print(
        "[human-bvh-debug] "
        f"source={source.display_name} raw_height={raw_debug.raw_height:.6g} "
        f"unit_scale={unit_scale:.6g} unit_reason={raw_debug.unit_reason!r} "
        f"up_axis={raw_debug.up_axis} lateral_axis={raw_debug.lateral_axis} "
        f"forward_axis={raw_debug.forward_axis} root_xyz_range={raw_debug.root_xyz_range} "
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
