from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.human_adapters import REPLAY_BODY_NAMES, load_bvh, load_human_mapping, motion_to_semantic
from scripts.human_adapters import pns, v3


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_BVH = PROJECT_ROOT / "tests" / "fixtures" / "minimal_human_maya.bvh"


class HumanAdapterPhase3Test(unittest.TestCase):
    def test_pns_discovery_scans_task_and_skips_intermediates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "pick_up"
            task_dir.mkdir()
            shutil.copy(FIXTURE_BVH, task_dir / "pick__up001_chr00.bvh")
            shutil.copy(FIXTURE_BVH, task_dir / "pick__up001_chr00_trimmed.bvh")
            shutil.copy(FIXTURE_BVH, task_dir / "pick__up001_chr00_soma.bvh")

            sources = pns.discover(task="pick_up", input_root=root)
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0].source_format, "pns_bvh")
            self.assertEqual(sources[0].output_stem, "pick__up001_chr00")

    def test_v3_discovery_scans_input_dir_and_parses_metadata_without_fbx(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp)
            shutil.copy(FIXTURE_BVH, input_dir / "Hand-Reaching7-a+b-1-wangchanghao.bvh")
            shutil.copy(FIXTURE_BVH, input_dir / "Hand-Reaching7-a+b-1-wangchanghao_tpose.bvh")

            sources = v3.discover(input_dir=input_dir)
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0].source_format, "v3_bvh")
            self.assertEqual(sources[0].base, "Hand-Reaching7-a+b-1")
            self.assertEqual(sources[0].person, "wangchanghao")

    def test_pns_semantic_skeleton_uses_foot_end_site_as_synthetic_toe(self) -> None:
        motion = load_bvh(FIXTURE_BVH)
        mapping = load_human_mapping(PROJECT_ROOT / "config" / "human_mappings" / "pns.json")
        semantic = motion_to_semantic(motion, mapping)

        self.assertEqual(semantic.positions.shape, (2, len(REPLAY_BODY_NAMES), 3))
        self.assertEqual(semantic.quaternions.shape, (2, len(REPLAY_BODY_NAMES), 4))
        self.assertEqual(semantic.body_names, REPLAY_BODY_NAMES)

        left_foot_idx = REPLAY_BODY_NAMES.index("left_foot")
        left_toe_idx = REPLAY_BODY_NAMES.index("left_toe")
        self.assertFalse(
            np.allclose(
                semantic.positions[:, left_foot_idx, :],
                semantic.positions[:, left_toe_idx, :],
            )
        )

        head_idx = REPLAY_BODY_NAMES.index("head")
        source_head_idx = motion.joint_names.index("Head")
        self.assertTrue(np.allclose(semantic.positions[:, head_idx, :], motion.positions[:, source_head_idx, :]))

    def test_hips_mean_position_uses_legs_but_quaternion_uses_root(self) -> None:
        motion = load_bvh(FIXTURE_BVH)
        root_idx = motion.joint_names.index("Hips")
        left_idx = motion.joint_names.index("LeftUpLeg")
        right_idx = motion.joint_names.index("RightUpLeg")
        quaternions = motion.quaternions.copy()
        quaternions[:, root_idx, :] = np.array([0.70710677, 0.0, 0.0, 0.70710677], dtype=np.float32)
        quaternions[:, left_idx, :] = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        quaternions[:, right_idx, :] = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        motion = type(motion)(
            path=motion.path,
            joint_names=motion.joint_names,
            positions=motion.positions,
            quaternions=quaternions,
            fps=motion.fps,
            frame_time=motion.frame_time,
        )
        mapping = load_human_mapping(PROJECT_ROOT / "config" / "human_mappings" / "pns.json")
        semantic = motion_to_semantic(motion, mapping)

        names = {name: idx for idx, name in enumerate(semantic.body_names)}
        expected_pos = 0.5 * (
            semantic.positions[:, names["left_up_leg"], :]
            + semantic.positions[:, names["right_up_leg"], :]
        )
        self.assertTrue(np.allclose(semantic.positions[:, names["hips_mean"], :], expected_pos))
        self.assertTrue(
            np.allclose(
                semantic.quaternions[:, names["hips_mean"], :],
                semantic.quaternions[:, names["hips"], :],
            )
        )

    def test_missing_head_and_toe_emit_warnings_and_fallbacks(self) -> None:
        motion = load_bvh(FIXTURE_BVH)
        mapping = load_human_mapping(PROJECT_ROOT / "config" / "human_mappings" / "pns.json")
        reduced_mapping = type(mapping)(
            path=mapping.path,
            description=mapping.description,
            mapping={
                key: value
                for key, value in mapping.mapping.items()
                if value not in {"head", "left_toe", "right_toe"}
            },
            aliases=mapping.aliases,
            required=mapping.required,
        )
        semantic = motion_to_semantic(motion, reduced_mapping)
        warning_text = "\n".join(semantic.warnings)
        self.assertIn("head missing", warning_text)
        self.assertIn("left_toe missing", warning_text)
        self.assertIn("right_toe missing", warning_text)


if __name__ == "__main__":
    unittest.main()
