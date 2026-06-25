"""Shared data structures for human BVH adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class BvhMotion:
    """World-space BVH FK result."""

    path: Path
    joint_names: list[str]
    positions: np.ndarray
    quaternions: np.ndarray
    fps: float
    frame_time: float


@dataclass(frozen=True)
class SourceMotion:
    """One BVH source motion discovered by an adapter."""

    motion_bvh: Path
    output_stem: str
    source_format: str
    display_name: str
    base: str = ""
    person: str = ""


@dataclass(frozen=True)
class HumanSemanticMotion:
    """BVH motion converted to the project semantic skeleton."""

    source: SourceMotion
    body_names: list[str]
    positions: np.ndarray
    quaternions: np.ndarray
    fps: float
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AxisDebugInfo:
    """Small diagnostic packet for unit and axis validation."""

    raw_height: float
    unit_scale: float
    unit_reason: str
    up_axis: str
    lateral_axis: str
    forward_axis: str
    root_xyz_range: tuple[float, float, float]
    head_minus_feet_mean: tuple[float, float, float]
    left_right_hip_delta_mean: tuple[float, float, float]
    foot_to_toe_delta_mean: tuple[float, float, float]


@dataclass(frozen=True)
class HumanMapping:
    """External BVH joint names mapped to project semantic names."""

    path: Path
    description: str
    mapping: dict[str, str]
    aliases: dict[str, str]
    required: tuple[str, ...]
