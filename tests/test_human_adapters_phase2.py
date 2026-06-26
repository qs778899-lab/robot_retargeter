from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from scripts.human_adapters import (
    AxisDebugInfo,
    axis_transform_to_mujoco,
    compute_axis_debug_info,
    load_bvh,
    load_human_mapping,
    transform_motion,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_BVH = PROJECT_ROOT / "tests" / "fixtures" / "minimal_human_maya.bvh"
NONROOT_POSITION_BVH = PROJECT_ROOT / "tests" / "fixtures" / "minimal_nonroot_position_channels.bvh"


class HumanAdapterPhase2Test(unittest.TestCase):
    def test_human_mapping_files_validate_required_joints(self) -> None:
        for mapping_name in ("pns.json", "v3.json"):
            mapping = load_human_mapping(PROJECT_ROOT / "config" / "human_mappings" / mapping_name)
            targets = set(mapping.mapping.values()) | set(mapping.aliases.values())
            for required in mapping.required:
                self.assertIn(required, targets)

    def test_minimal_bvh_fk_shape_and_frame_metadata(self) -> None:
        motion = load_bvh(FIXTURE_BVH)
        self.assertEqual(motion.positions.shape, (2, len(motion.joint_names), 3))
        self.assertEqual(motion.quaternions.shape, (2, len(motion.joint_names), 4))
        self.assertAlmostEqual(motion.fps, 30.0, places=3)
        self.assertIn("Hips", motion.joint_names)
        self.assertIn("LeftFoot_EndSite", motion.joint_names)
        self.assertIn("RightFoot_EndSite", motion.joint_names)

    def test_nonroot_position_channels_are_not_added_to_offsets_twice(self) -> None:
        motion = load_bvh(NONROOT_POSITION_BVH)
        names = {name: idx for idx, name in enumerate(motion.joint_names)}
        self.assertAlmostEqual(float(motion.positions[0, names["Head"], 1]), 10.0)
        self.assertAlmostEqual(float(motion.positions[0, names["LeftFoot"], 1]), -10.0)
        feet_center = 0.5 * (
            motion.positions[0, names["LeftFoot"], :] + motion.positions[0, names["RightFoot"], :]
        )
        raw_height = float(np.max(np.abs(motion.positions[0, names["Head"], :] - feet_center)))
        self.assertAlmostEqual(raw_height, 20.0)

    def test_unit_and_axis_debug_info_for_maya_centimeter_fixture(self) -> None:
        motion = load_bvh(FIXTURE_BVH)
        debug = compute_axis_debug_info(motion)
        self.assertAlmostEqual(debug.raw_height, 190.0)
        self.assertAlmostEqual(debug.unit_scale, 0.01)
        self.assertEqual(debug.up_axis, "+y")
        self.assertEqual(debug.lateral_axis, "+x")
        self.assertEqual(debug.forward_axis, "+z")

    def test_axis_transform_converts_maya_to_mujoco_frame(self) -> None:
        motion = load_bvh(FIXTURE_BVH)
        transformed = transform_motion(motion, unit_scale=0.01)
        names = {name: idx for idx, name in enumerate(transformed.joint_names)}
        head_z = transformed.positions[:, names["Head_EndSite"], 2].mean()
        feet_z = transformed.positions[
            :, [names["LeftFoot_EndSite"], names["RightFoot_EndSite"]], 2
        ].mean()
        self.assertGreater(head_z, feet_z)

        left_hip = transformed.positions[:, names["LeftUpLeg"], :].mean(axis=0)
        right_hip = transformed.positions[:, names["RightUpLeg"], :].mean(axis=0)
        self.assertGreater((left_hip - right_hip)[1], 0.0)

        foot_to_toe = (
            transformed.positions[:, names["LeftFoot_EndSite"], :]
            - transformed.positions[:, names["LeftFoot"], :]
        ).mean(axis=0)
        self.assertGreater(foot_to_toe[0], 0.0)
        self.assertLess(abs(foot_to_toe[1]), 1e-6)

        quat_norms = np.linalg.norm(transformed.quaternions, axis=-1)
        self.assertTrue(np.allclose(quat_norms, 1.0, atol=1e-6))

    def test_auto_axis_transform_supports_non_maya_v3_axes(self) -> None:
        debug = AxisDebugInfo(
            raw_height=304.0,
            unit_scale=0.01,
            unit_reason="test",
            up_axis="+y",
            lateral_axis="-z",
            forward_axis="+x",
            root_xyz_range=(0.0, 0.0, 0.0),
            head_minus_feet_mean=(0.0, 304.0, 0.0),
            left_right_hip_delta_mean=(0.0, 0.0, -30.0),
            foot_to_toe_delta_mean=(20.0, 0.0, 0.0),
        )
        transform = axis_transform_to_mujoco(debug)
        self.assertTrue(np.allclose(transform @ np.array([1.0, 0.0, 0.0]), [1.0, 0.0, 0.0]))
        self.assertTrue(np.allclose(transform @ np.array([0.0, 1.0, 0.0]), [0.0, 0.0, 1.0]))
        self.assertTrue(np.allclose(transform @ np.array([0.0, 0.0, -1.0]), [0.0, 1.0, 0.0]))


if __name__ == "__main__":
    unittest.main()
