from __future__ import annotations

import pickle
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_BVH = PROJECT_ROOT / "tests" / "fixtures" / "minimal_human_maya.bvh"


class HumanReplayPhase4Test(unittest.TestCase):
    def test_pns_foot_orientation_override_is_registered(self) -> None:
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        try:
            from human_replay import FOOT_ORIENTATION_KEYPOINTS_BY_FORMAT
        finally:
            sys.path.pop(0)

        pns_overrides = FOOT_ORIENTATION_KEYPOINTS_BY_FORMAT["pns"]
        self.assertEqual(pns_overrides["left_calf"][0], "left_foot")
        self.assertEqual(pns_overrides["right_calf"][0], "right_foot")
        self.assertTrue(np.allclose(pns_overrides["left_calf"][1], [0.0, 90.0, 0.0]))
        self.assertTrue(np.allclose(pns_overrides["right_calf"][1], [0.0, 90.0, 0.0]))

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
