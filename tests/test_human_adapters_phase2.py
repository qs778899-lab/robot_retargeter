from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from scripts.human_adapters import (
    compute_axis_debug_info,
    load_bvh,
    load_human_mapping,
    transform_motion,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_BVH = PROJECT_ROOT / "tests" / "fixtures" / "minimal_human_maya.bvh"


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


if __name__ == "__main__":
    unittest.main()
