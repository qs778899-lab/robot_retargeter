# Log

## 2026-06-25

- 阅读 `/home/lab/Desktop/soma-retargeter` 中 `tools/batch_retarget_bvh.py`、`tools/batch_retarget.py`、`tools/mappings/pns.json`、`tools/mappings/v3.json`、`tools/human_adapters/*`、`tools/batch_workflow.py`。
- 阅读 `/home/lab/Desktop/robot_retargeter/AGENTS.md`、`scripts/smpl_replay.py`、`scripts/robot_replay.py`、`scripts/robot_retarget.py`、`config/skeleton/skeleton.yaml`、`config/robot/g1.yaml`。
- 确认目标仓库当前 retarget 核心输入是 keypoints pkl，不是 BVH；PNS/v3 应接入到 BVH -> 标准 keypoints pkl 的 adapter 层。
- 写入 `plan.md`、`status.md`、`test_matrix.md`。
- 根据用户补充要求，收敛范围为只适配 PNS/v3 两种 BVH 骨架格式；移除 FBX 文件适配、FBX T-pose、Blender、BVH-FBX 配对校验相关计划。
- 复查 PNS 样例 `assets/motions/bvh/pick_up/pick__up745_chr00.bvh`：`LeftFoot/RightFoot` 下存在 `End Site`，offset 为 `0, -10, 15.12`，应作为 synthetic toe/contact 点处理；PNS 样例也存在命名 `Head` joint，计划改为优先直接映射 `Head`。
- 补充坐标系风险的具体避免和排查方法：集中定义轴变换，position/quaternion 同步变换，输出 root/head/foot/toe debug 统计，并给出躺倒、侧身、镜像、全身 IK 误差大的判定流程。
- 补充阶段门禁规则：每个 phase 必须执行 `test_matrix.md` 对应章节的全部测试，全部通过后才能更新 `status.md` 并进入下一阶段；失败时停留在当前 phase 修复并重跑。
- 用户指出 BVH 单位/朝向规则只针对特定类似 task，长规则不宜全部放进根 `AGENTS.md`。调整为：根 `AGENTS.md` 只保留触发规则和必读指针，详细规则迁移到 `docs/human_bvh_intake.md`；当前计划同步引用专项文档。

## Phase 2

- 新增 `scripts/human_adapters/base.py`、`bvh_parser.py`、`mappings.py`。
- 新增 `config/human_mappings/pns.json` 和 `config/human_mappings/v3.json`。
- 新增最小 Maya/Y-up BVH fixture 与 `tests/test_human_adapters_phase2.py`。
- 运行 `python -m py_compile scripts/human_adapters/*.py`：通过。
- 运行 `python -m unittest tests.test_human_adapters_phase2`：通过，4 个测试覆盖 mapping 校验、BVH FK、单位判定、朝向判定和 Maya -> MuJoCo 坐标变换。

## Phase 3

- 新增 `scripts/human_adapters/discovery.py`、`pns.py`、`v3.py`、`keypoints.py`。
- 扩展 `base.py`，加入 `SourceMotion` 和 `HumanSemanticMotion`。
- 新增 `tests/test_human_adapters_phase3.py`。
- 运行 `python -m py_compile scripts/human_adapters/*.py`：通过。
- 运行 `python -m unittest tests.test_human_adapters_phase3`：通过，4 个测试覆盖 PNS discovery skip、中间文件过滤、v3 metadata、semantic skeleton shape、PNS foot End Site -> toe、Head 直接映射和缺失 fallback warning。
- 回归运行 `python -m unittest tests.test_human_adapters_phase2`：通过。

## Phase 4

- 新增 `scripts/human_replay.py`，支持 PNS/v3 BVH 到 keypoints pkl 的 no-viewer 转换。
- 为避免入口依赖完整 SMPL 环境，`human_replay.py` 不 import `smpl_replay.py`；它使用轻量 YAML 片段解析、MuJoCo link length 计算和本地 keypoints pkl 保存。
- 新增 `tests/test_human_replay_phase4.py`。
- 运行 `python -m py_compile scripts/human_adapters/*.py scripts/human_replay.py`：通过。
- 运行 `python -m unittest tests.test_human_replay_phase4`：通过，覆盖 `--help`、单 BVH no-viewer smoke、pkl 字段/shape 和单位/朝向 debug 日志。
- 回归运行 `python -m unittest tests.test_human_adapters_phase2 tests.test_human_adapters_phase3 tests.test_human_replay_phase4`：通过，10 个测试全部通过。

## Phase 5

- 使用 `/home/lab/miniconda3/envs/robot_retargeter/bin/python` 执行端到端 smoke。
- PNS smoke：`scripts/human_replay.py --format pns --input-bvh tests/fixtures/minimal_human_maya.bvh --robot-config config/robot/g1.yaml --skeleton-config config/skeleton/skeleton.yaml --no-viewer` 生成 `output_data/keypoints/g1/minimal_human_maya_keypoints.pkl`。
- v3 smoke：`scripts/human_replay.py --format v3 --input-bvh tests/fixtures/minimal_human_v3_maya.bvh --robot-config config/robot/g1.yaml --skeleton-config config/skeleton/skeleton.yaml --no-viewer` 生成 `output_data/keypoints/g1/minimal_human_v3_maya_keypoints.pkl`。
- 两条 smoke 均输出单位/朝向 debug：raw height 为厘米级，`unit_scale=0.01`，source axes 为 `up_axis=+y`、`lateral_axis=+x`、`forward_axis=+z`。
- PNS retarget：`scripts/robot_retarget.py --config config/robot/g1.yaml --keypoints-name minimal_human_maya --no-render-debug` 生成 `output_data/robot_motion/minimal_human_maya_g1.csv`，shape 为 `(2, 36)`。
- v3 retarget：`scripts/robot_retarget.py --config config/robot/g1.yaml --keypoints-name minimal_human_v3_maya --no-render-debug` 生成 `output_data/robot_motion/minimal_human_v3_maya_g1.csv`，shape 为 `(2, 36)`。
- CSV 行数检查：两份输出均为 2 行，等于 fixture 有效帧数。
- 最终回归：`python -m unittest tests.test_human_adapters_phase2 tests.test_human_adapters_phase3 tests.test_human_replay_phase4` 通过，10 个测试全部通过。
