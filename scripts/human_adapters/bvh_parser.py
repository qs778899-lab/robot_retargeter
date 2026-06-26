"""BVH hierarchy parser, FK, unit inference, and axis conversion."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from .base import AxisDebugInfo, BvhMotion

MAYA_TO_MUJOCO = np.array(
    [
        [0.0, 0.0, 1.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ],
    dtype=np.float64,
)

AXIS_NAMES = ("x", "y", "z")


@dataclass
class BvhNode:
    name: str
    offset: np.ndarray
    channels: list[str] = field(default_factory=list)
    children: list["BvhNode"] = field(default_factory=list)
    is_end_site: bool = False


class _BvhReader:
    def __init__(self, lines: list[str]):
        self.lines = [line.strip() for line in lines if line.strip()]
        self.index = 0
        self.animated_nodes: list[BvhNode] = []
        self.all_nodes: list[BvhNode] = []

    def parse(self) -> tuple[BvhNode, list[BvhNode], list[BvhNode], np.ndarray, float]:
        self._expect("HIERARCHY")
        root = self._parse_joint(parent_name=None)
        self._expect("MOTION")
        frames_line = self._take()
        if not frames_line.startswith("Frames:"):
            raise ValueError(f"Expected 'Frames:', got {frames_line!r}")
        frame_count = int(frames_line.split(":", 1)[1].strip())

        frame_time_line = self._take()
        if not frame_time_line.startswith("Frame Time:"):
            raise ValueError(f"Expected 'Frame Time:', got {frame_time_line!r}")
        frame_time = float(frame_time_line.split(":", 1)[1].strip())

        frames: list[list[float]] = []
        channel_count = sum(len(node.channels) for node in self.animated_nodes)
        for _ in range(frame_count):
            values = [float(item) for item in self._take().split()]
            if len(values) != channel_count:
                raise ValueError(
                    f"BVH frame has {len(values)} values, expected {channel_count}"
                )
            frames.append(values)
        return root, self.animated_nodes, self.all_nodes, np.asarray(frames), frame_time

    def _parse_joint(self, parent_name: str | None) -> BvhNode:
        header = self._take()
        parts = header.split()
        if parts[0] == "ROOT" or parts[0] == "JOINT":
            if len(parts) != 2:
                raise ValueError(f"Invalid joint header: {header}")
            node = BvhNode(name=parts[1], offset=np.zeros(3, dtype=np.float64))
            self.animated_nodes.append(node)
        elif header == "End Site":
            if parent_name is None:
                raise ValueError("End Site cannot be root")
            node = BvhNode(
                name=f"{parent_name}_EndSite",
                offset=np.zeros(3, dtype=np.float64),
                is_end_site=True,
            )
        else:
            raise ValueError(f"Expected joint header, got {header!r}")

        self.all_nodes.append(node)
        self._expect("{")
        while True:
            line = self._take()
            if line == "}":
                return node
            if line.startswith("OFFSET"):
                values = [float(item) for item in line.split()[1:]]
                if len(values) != 3:
                    raise ValueError(f"Invalid OFFSET line: {line}")
                node.offset = np.asarray(values, dtype=np.float64)
                continue
            if line.startswith("CHANNELS"):
                parts = line.split()
                count = int(parts[1])
                channels = parts[2:]
                if len(channels) != count:
                    raise ValueError(f"Invalid CHANNELS line: {line}")
                node.channels = channels
                continue
            if line.startswith("JOINT") or line == "End Site":
                self.index -= 1
                node.children.append(self._parse_joint(parent_name=node.name))
                continue
            raise ValueError(f"Unexpected BVH line: {line}")

    def _take(self) -> str:
        if self.index >= len(self.lines):
            raise ValueError("Unexpected end of BVH")
        line = self.lines[self.index]
        self.index += 1
        return line

    def _expect(self, expected: str) -> None:
        got = self._take()
        if got != expected:
            raise ValueError(f"Expected {expected!r}, got {got!r}")


def load_bvh(path: Path | str) -> BvhMotion:
    bvh_path = Path(path)
    reader = _BvhReader(bvh_path.read_text(encoding="utf-8").splitlines())
    root, animated_nodes, all_nodes, frame_values, frame_time = reader.parse()
    positions, quaternions = _run_fk(root, animated_nodes, all_nodes, frame_values)
    fps = 1.0 / frame_time if frame_time > 0.0 else 0.0
    return BvhMotion(
        path=bvh_path,
        joint_names=[node.name for node in all_nodes],
        positions=positions.astype(np.float32),
        quaternions=quaternions.astype(np.float32),
        fps=float(fps),
        frame_time=float(frame_time),
    )


def _run_fk(
    root: BvhNode,
    animated_nodes: list[BvhNode],
    all_nodes: list[BvhNode],
    frame_values: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    node_to_idx = {id(node): idx for idx, node in enumerate(all_nodes)}
    channel_offsets: dict[int, int] = {}
    cursor = 0
    for node in animated_nodes:
        channel_offsets[id(node)] = cursor
        cursor += len(node.channels)

    frame_count = frame_values.shape[0]
    positions = np.zeros((frame_count, len(all_nodes), 3), dtype=np.float64)
    quaternions = np.zeros((frame_count, len(all_nodes), 4), dtype=np.float64)

    for frame_idx in range(frame_count):
        _fk_node(
            node=root,
            frame=frame_values[frame_idx],
            channel_offsets=channel_offsets,
            node_to_idx=node_to_idx,
            positions=positions[frame_idx],
            quaternions=quaternions[frame_idx],
            parent_pos=np.zeros(3, dtype=np.float64),
            parent_rot=Rotation.identity(),
        )
    return positions, quaternions


def _fk_node(
    *,
    node: BvhNode,
    frame: np.ndarray,
    channel_offsets: dict[int, int],
    node_to_idx: dict[int, int],
    positions: np.ndarray,
    quaternions: np.ndarray,
    parent_pos: np.ndarray,
    parent_rot: Rotation,
) -> None:
    translation = np.zeros(3, dtype=np.float64)
    local_rot = Rotation.identity()
    has_position_channels = False
    if not node.is_end_site:
        values = frame[
            channel_offsets[id(node)] : channel_offsets[id(node)] + len(node.channels)
        ]
        for channel, value in zip(node.channels, values):
            axis = channel[0].lower()
            if channel.endswith("position"):
                has_position_channels = True
                translation["xyz".index(axis)] = value
            elif channel.endswith("rotation"):
                local_rot = local_rot * Rotation.from_euler(axis, value, degrees=True)
            else:
                raise ValueError(f"Unsupported BVH channel: {channel}")

    local_pos = translation if has_position_channels else node.offset
    world_pos = parent_pos + parent_rot.apply(local_pos)
    world_rot = parent_rot * local_rot

    idx = node_to_idx[id(node)]
    positions[idx] = world_pos
    quat_xyzw = world_rot.as_quat()
    quaternions[idx] = quat_xyzw[[3, 0, 1, 2]]

    for child in node.children:
        _fk_node(
            node=child,
            frame=frame,
            channel_offsets=channel_offsets,
            node_to_idx=node_to_idx,
            positions=positions,
            quaternions=quaternions,
            parent_pos=world_pos,
            parent_rot=world_rot,
        )


def infer_unit_scale(raw_height: float) -> tuple[float, str]:
    if 1.0 <= raw_height <= 2.5:
        return 1.0, "raw_height is in meter-scale human range"
    if 80.0 <= raw_height <= 400.0:
        return 0.01, "raw_height is in centimeter-scale human range"
    if 800.0 <= raw_height <= 4000.0:
        return 0.001, "raw_height is in millimeter-scale human range"
    return 1.0, "raw_height is outside standard ranges; unit_scale left explicit"


def axis_transform_to_mujoco(debug_info: AxisDebugInfo) -> np.ndarray:
    """Build a source->MuJoCo axis transform from measured BVH axes."""

    transform = np.zeros((3, 3), dtype=np.float64)
    for target_axis_idx, source_axis in enumerate(
        (debug_info.forward_axis, debug_info.lateral_axis, debug_info.up_axis)
    ):
        sign, axis_name = _parse_signed_axis(source_axis)
        transform[target_axis_idx, AXIS_NAMES.index(axis_name)] = sign

    determinant = round(float(np.linalg.det(transform)))
    if abs(determinant) != 1:
        raise ValueError(f"Invalid axis transform from debug info: {debug_info}")
    if determinant < 0:
        raise ValueError(
            "BVH axes form a left-handed transform; verify forward/lateral/up debug output"
        )
    return transform


def transform_motion(
    motion: BvhMotion,
    *,
    unit_scale: float,
    axis_transform: np.ndarray = MAYA_TO_MUJOCO,
) -> BvhMotion:
    positions = np.einsum(
        "ij,tkj->tki", axis_transform, motion.positions.astype(np.float64) * unit_scale
    )
    rot_mats = Rotation.from_quat(
        motion.quaternions[..., [1, 2, 3, 0]].reshape(-1, 4)
    ).as_matrix()
    transformed_mats = axis_transform @ rot_mats @ axis_transform.T
    transformed_quats_xyzw = Rotation.from_matrix(transformed_mats).as_quat()
    transformed_quats_wxyz = transformed_quats_xyzw[:, [3, 0, 1, 2]].reshape(
        motion.quaternions.shape
    )
    return BvhMotion(
        path=motion.path,
        joint_names=list(motion.joint_names),
        positions=positions.astype(np.float32),
        quaternions=transformed_quats_wxyz.astype(np.float32),
        fps=motion.fps,
        frame_time=motion.frame_time,
    )


def compute_axis_debug_info(
    motion: BvhMotion,
    *,
    unit_scale: float | None = None,
) -> AxisDebugInfo:
    names = {name: idx for idx, name in enumerate(motion.joint_names)}
    head_idx = _first_existing(names, ("Head_EndSite", "Head"))
    foot_indices = [
        idx
        for idx in (
            _first_existing(names, ("LeftFoot_EndSite", "LeftToeBase", "LeftFoot")),
            _first_existing(names, ("RightFoot_EndSite", "RightToeBase", "RightFoot")),
        )
        if idx is not None
    ]
    if head_idx is None or not foot_indices:
        raise ValueError("Cannot compute raw height without head and foot joints")

    feet_center = motion.positions[:, foot_indices, :].mean(axis=1)
    head_minus_feet = motion.positions[:, head_idx, :] - feet_center
    mean_head_minus_feet = head_minus_feet.mean(axis=0)
    raw_height = float(np.max(np.abs(mean_head_minus_feet)))
    inferred_scale, unit_reason = infer_unit_scale(raw_height)
    effective_unit_scale = inferred_scale if unit_scale is None else float(unit_scale)

    lateral_delta = _mean_delta(
        motion,
        names,
        ("LeftShoulder", "LeftArm", "LeftUpLeg"),
        ("RightShoulder", "RightArm", "RightUpLeg"),
    )
    forward_delta = _mean_delta(
        motion,
        names,
        ("LeftFoot_EndSite", "LeftToeBase"),
        ("LeftFoot",),
        fallback=np.zeros(3, dtype=np.float32),
    )
    if np.allclose(forward_delta, 0.0):
        forward_delta = _mean_delta(
            motion,
            names,
            ("RightFoot_EndSite", "RightToeBase"),
            ("RightFoot",),
            fallback=np.zeros(3, dtype=np.float32),
        )

    root_idx = names.get("Hips", 0)
    root_range = np.ptp(motion.positions[:, root_idx, :], axis=0)

    return AxisDebugInfo(
        raw_height=raw_height,
        unit_scale=effective_unit_scale,
        unit_reason=unit_reason,
        up_axis=_dominant_axis(mean_head_minus_feet),
        lateral_axis=_dominant_axis(lateral_delta),
        forward_axis=_dominant_axis(forward_delta),
        root_xyz_range=tuple(float(v) for v in root_range),
        head_minus_feet_mean=tuple(float(v) for v in mean_head_minus_feet),
        left_right_hip_delta_mean=tuple(float(v) for v in lateral_delta),
        foot_to_toe_delta_mean=tuple(float(v) for v in forward_delta),
    )


def _first_existing(names: dict[str, int], candidates: tuple[str, ...]) -> int | None:
    for candidate in candidates:
        if candidate in names:
            return names[candidate]
    return None


def _mean_delta(
    motion: BvhMotion,
    names: dict[str, int],
    positive_candidates: tuple[str, ...],
    negative_candidates: tuple[str, ...],
    fallback: np.ndarray | None = None,
) -> np.ndarray:
    positive_idx = _first_existing(names, positive_candidates)
    negative_idx = _first_existing(names, negative_candidates)
    if positive_idx is None or negative_idx is None:
        if fallback is not None:
            return fallback
        raise ValueError(f"Missing joints for delta: {positive_candidates}, {negative_candidates}")
    return (motion.positions[:, positive_idx, :] - motion.positions[:, negative_idx, :]).mean(
        axis=0
    )


def _dominant_axis(vector: np.ndarray) -> str:
    idx = int(np.argmax(np.abs(vector)))
    sign = "+" if vector[idx] >= 0.0 else "-"
    return f"{sign}{AXIS_NAMES[idx]}"


def _parse_signed_axis(axis: str) -> tuple[float, str]:
    if len(axis) != 2 or axis[0] not in {"+", "-"} or axis[1] not in AXIS_NAMES:
        raise ValueError(f"Invalid signed axis: {axis!r}")
    return (1.0 if axis[0] == "+" else -1.0), axis[1]
