from __future__ import annotations

import pickle
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_BVH = PROJECT_ROOT / "tests" / "fixtures" / "minimal_human_maya.bvh"


class HumanReplayPhase4Test(unittest.TestCase):
    def test_bvh_foot_frame_orientation_overrides_are_registered(self) -> None:
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        try:
            from human_replay import FOOT_FRAME_KEYPOINTS_BY_FORMAT, THIGH_FRAME_KEYPOINTS_BY_FORMAT
        finally:
            sys.path.pop(0)

        for source_format in ("pns", "v3"):
            thigh_overrides = THIGH_FRAME_KEYPOINTS_BY_FORMAT[source_format]
            self.assertEqual(thigh_overrides["left_thigh"], ("left_hip", "left_thigh"))
            self.assertEqual(thigh_overrides["right_thigh"], ("right_hip", "right_thigh"))

            overrides = FOOT_FRAME_KEYPOINTS_BY_FORMAT[source_format]
            self.assertEqual(
                overrides["left_calf"],
                ("left_thigh", "left_calf", "left_foot", "left_toe"),
            )
            self.assertEqual(
                overrides["right_calf"],
                ("right_thigh", "right_calf", "right_foot", "right_toe"),
            )

    def test_thigh_frame_orientation_uses_pelvis_facing_for_twist(self) -> None:
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        try:
            from human_replay import apply_format_thigh_orientation_overrides
        finally:
            sys.path.pop(0)

        keypoint_names = ["hips_mean", "left_hip", "left_thigh", "right_hip", "right_thigh"]
        positions = np.zeros((1, len(keypoint_names), 3), dtype=np.float32)
        idx = {name: i for i, name in enumerate(keypoint_names)}
        positions[0, idx["left_hip"]] = [0.0, 0.10, 1.0]
        positions[0, idx["right_hip"]] = [0.0, -0.10, 1.0]
        positions[0, idx["left_thigh"]] = [0.0, 0.10, 0.5]
        positions[0, idx["right_thigh"]] = [0.0, -0.10, 0.5]
        quaternions = np.zeros((1, len(keypoint_names), 4), dtype=np.float32)
        quaternions[:, :, 0] = 1.0

        adjusted = apply_format_thigh_orientation_overrides(
            source_format="pns",
            keypoint_names=keypoint_names,
            keypoint_positions=positions,
            keypoint_quaternions=quaternions,
        )

        for name in ("left_thigh", "right_thigh"):
            rot = Rotation.from_quat(adjusted[0, idx[name], [1, 2, 3, 0]])
            self.assertTrue(np.allclose(rot.apply([1.0, 0.0, 0.0]), [1.0, 0.0, 0.0], atol=1e-6))
            self.assertTrue(np.allclose(rot.apply([0.0, 0.0, 1.0]), [0.0, 0.0, 1.0], atol=1e-6))

    def test_human_replay_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/human_replay.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--format", result.stdout)
        self.assertIn("--input-bvh", result.stdout)

    def test_single_bvh_no_viewer_smoke_generates_keypoints_pkl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/human_replay.py",
                    "--format",
                    "pns",
                    "--input-bvh",
                    str(FIXTURE_BVH),
                    "--robot-config",
                    "config/robot/g1.yaml",
                    "--skeleton-config",
                    "config/skeleton/skeleton.yaml",
                    "--output-dir",
                    str(output_dir),
                    "--no-viewer",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("[human-bvh-debug]", result.stdout)
            self.assertIn("raw_height=", result.stdout)
            self.assertIn("unit_scale=", result.stdout)
            self.assertIn("up_axis=", result.stdout)
            self.assertIn("lateral_axis=", result.stdout)
            self.assertIn("forward_axis=", result.stdout)

            output_path = output_dir / f"{FIXTURE_BVH.stem}_keypoints.pkl"
            self.assertTrue(output_path.is_file())
            with output_path.open("rb") as f:
                payload = pickle.load(f)

            for key in ("keypoint_names", "positions", "quaternions", "fps", "contact_names", "contact_states"):
                self.assertIn(key, payload)
            self.assertEqual(payload["positions"].shape[0], 2)
            self.assertEqual(payload["positions"].shape[-1], 3)
            self.assertEqual(payload["quaternions"].shape[0], 2)
            self.assertEqual(payload["quaternions"].shape[-1], 4)
            self.assertEqual(payload["contact_states"].shape, (2, 0))
            self.assertEqual(len(payload["keypoint_names"]), payload["positions"].shape[1])
            orientation_scales = payload["ik_orientation_cost_scales"]
            self.assertEqual(orientation_scales["left_arm"], 0.0)
            self.assertEqual(orientation_scales["right_fore_arm"], 0.0)
            self.assertIn("z_shift=", result.stdout)

            keypoint_idx = {name: idx for idx, name in enumerate(payload["keypoint_names"])}
            support_z = payload["positions"][
                :,
                [keypoint_idx["left_calf"], keypoint_idx["right_calf"]],
                2,
            ]
            self.assertLess(float(support_z.min()), 0.1)
            self.assertGreater(float(support_z.min()), -1e-4)


if __name__ == "__main__":
    unittest.main()
