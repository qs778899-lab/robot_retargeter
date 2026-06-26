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

## 2026-06-26：可视化问题排查与修复

- 用户可视化完整 PNS/v3 robot motion 后反馈两个问题：机器人整体悬空；双臂肘部会往身体中线凹陷。
- 复现数据：
  - PNS：`/home/lab/Downloads/pick_up/pick_up2274_chr00.bvh`，1835 帧。
  - v3：`/home/lab/Desktop/soma-retargeter_v12_experiment/assets/motions/v3_test/bvh/Hand-Reaching-62-pangyiming-v3-1-pangyiming-v3.bvh`，208 帧。
- 数值诊断：
  - 修复前 keypoints 支撑点最低 Z 约 `1.20m ~ 1.26m`，BVH 世界 root offset 被原样带入 IK，是机器人悬空的直接原因。
  - PNS raw axis：`up=+y, lateral=+x, forward=+z`，固定 Maya 矩阵成立。
  - v3 raw axis：`up=+y, lateral=-z, forward=+x`，固定 Maya 矩阵错误，会把左右轴映射到 MuJoCo 前后方向，是 v3 手臂左右目标异常的直接原因。
  - PNS/v3 mapping 未接入 `LeftShoulder/RightShoulder`，`shoulder_mean` 只能从左右上臂平均，肩中心不够稳定。
- 修复：
  - `scripts/human_adapters/bvh_parser.py`：扩大 cm/mm 单位自动判定范围；新增 `axis_transform_to_mujoco()`，按实测 forward/lateral/up 构造 source -> MuJoCo 矩阵。
  - `scripts/human_replay.py`：`--facing-direction` 默认改为 `auto`；debug 输出 `axis_transform`；写出 keypoints 前用目标机器人支撑 body 高度做 ground alignment，并输出 `ground_links/observed_ground_z/target_ground_z/z_shift`。
  - `config/human_mappings/pns.json`、`config/human_mappings/v3.json`：补充 `LeftShoulder/RightShoulder`。
  - `scripts/human_adapters/keypoints.py`：`shoulder_mean` 优先使用真实左右肩点，缺失时才回退到左右上臂。
  - `docs/human_bvh_intake.md`、`plan.md`、`test_matrix.md`：补充自动轴变换、地面对齐和肘部内凹排查门禁。
- 验证：
  - `/home/lab/miniconda3/envs/robot_retargeter/bin/python -m py_compile scripts/human_adapters/*.py scripts/human_replay.py`：通过。
  - `/home/lab/miniconda3/envs/robot_retargeter/bin/python -m unittest tests.test_human_adapters_phase2 tests.test_human_adapters_phase3 tests.test_human_replay_phase4`：通过，11 个测试。
  - PNS 完整链路重新生成：`output_data/robot_motion/pick_up2274_chr00_g1.csv`，shape `(1835, 36)`。
  - v3 完整链路重新生成：`output_data/robot_motion/Hand-Reaching-62-pangyiming-v3-1-pangyiming-v3_g1.csv`，shape `(208, 36)`。
  - FK 抽样检查：
    - PNS root_z `[min=0.5638, mean=0.8351, max=0.8704]`，足端 sampled Z `[min=-0.0154, mean=0.0563, max=0.0684]`。
    - v3 root_z `[min=0.7807, mean=0.7887, max=0.8022]`，足端 sampled Z `[min=-0.0225, mean=-0.0087, max=0.0090]`。
    - v3 手臂目标左右关系修正：左臂相对肩中心 Y 全为正，右臂 Y 全为负。

## 2026-06-26：手臂仍异常与 v3 腿歪的二次排查

- 用户复查可视化后反馈：`Hand-Reaching-62-pangyiming-v3-1-pangyiming-v3` 手臂问题仍存在，腿也歪斜。
- 继续拆分位置链和 orientation 链：
  - 发现 PNS/v3 BVH 的很多非 root joint 同时有 `OFFSET` 和 `X/Y/Zposition`，且 frame 0 的 position channel 等于 offset。
  - 原 FK 使用 `local_pos = OFFSET + translation`，导致骨段长度被加两次。修复前 PNS/v3 raw height 约 `314cm/304cm`，修复后为 `170.274cm/152.202cm`。
  - `scripts/human_adapters/bvh_parser.py` 改为：有 position channel 的 node 使用 channel translation 作为 local position；没有 position channel 的 node 才使用 OFFSET。
- 手臂单独隔离：
  - 新的 robot-frame 几何 quaternion 已能让关键腿/手 link 的 `cos(rotated_rest_vec, target_vec)` 达到 `1.0`。
  - 但 v3 标准配置下右臂位置误差仍高：`right_arm mean/max = 0.1216/0.1917m`，`right_fore_arm mean/max = 0.0957/0.1614m`。
  - 临时把手臂 orientation cost 置 0 后，同一 keypoints 下误差降为：
    - `left_arm mean/max = 0.0183/0.0455m`
    - `left_fore_arm mean/max = 0.0149/0.0448m`
    - `right_arm mean/max = 0.0249/0.0477m`
    - `right_fore_arm mean/max = 0.0207/0.0511m`
  - 结论：手臂目标位置是合理的，异常来自 BVH 手臂 roll/orientation 与 G1 肩肘自由度冲突。
- 修复：
  - `scripts/human_replay.py` 写出的 human BVH keypoints pkl 增加 `ik_orientation_cost_scales`，默认将 `left/right_shoulder`、`left/right_arm`、`left/right_fore_arm` orientation scale 设为 `0.0`。
  - `scripts/robot_retarget.py` 读取可选 `ik_orientation_cost_scales` 并按 keypoint 缩放 orientation cost；payload 不含该字段时保持原行为不变。
  - `scripts/human_replay.py` 输出 quaternion 改为直接用目标机器人 rest link frame 构造：把目标机器人初始 link 向量旋到当前 keypoint link 向量，再乘目标机器人初始 body quaternion，避免源 BVH/SMPL 局部轴假设污染 robot frame。
- 验证：
  - `/home/lab/miniconda3/envs/robot_retargeter/bin/python -m py_compile scripts/human_adapters/*.py scripts/human_replay.py scripts/robot_retarget.py`：通过。
  - `/home/lab/miniconda3/envs/robot_retargeter/bin/python -m unittest tests.test_human_adapters_phase2 tests.test_human_adapters_phase3 tests.test_human_replay_phase4`：通过，12 个测试。
  - v3 标准链路重新生成 `output_data/robot_motion/Hand-Reaching-62-pangyiming-v3-1-pangyiming-v3_g1.csv`，shape `(208, 36)`。
  - PNS 标准链路重新生成 `output_data/robot_motion/pick_up2274_chr00_g1.csv`，shape `(1835, 36)`。
  - v3 标准链路最终抽样：root_z `[0.7840, 0.7885, 0.7994]`，foot sampled Z `[-0.0030, 0.0022, 0.0103]`；手臂位置误差保持在约 `1.5cm ~ 5.1cm`。

## 2026-06-26：版本切分前的 PNS 遗留问题记录

- 用户确认 v3 `Hand-Reaching-62-pangyiming-v3-1-pangyiming-v3` 可视化已经正常。
- 用户继续反馈 PNS `pick_up2274_chr00` 腿部仍异常：两条腿大腿以下相对大腿会转出奇怪角度，转身后有时交叉脚。
- 当前初步数值诊断：
  - PNS robot motion 和 keypoints 中的交叉脚样本数一致：采样中 `target_cross_count=38`、`robot_cross_count=38`，说明 IK 在跟随目标，不是独立产生交叉。
  - PNS 足端 sampled Z 仍有局部穿地：约 `min=-0.1335m`，需要继续结合 contact/ground alignment 检查。
  - PNS `left_hip` position error 和 rotation error 偏大，提示 root/facing、局部腿目标或 pelvis orientation 仍可能有问题。
- 后续排查方向：
  - 不回退 v3 已验证修复。
  - 针对 PNS 转身动作，比较全局左右脚交换与以 pelvis/root facing 为基准的局部左右关系。
  - 检查 root yaw/hips_mean orientation 是否应参与 position target 的局部化或 foot target 的 facing correction。
  - 检查 PNS synthetic toe/foot End Site 是否适合作为腿部/接触参考，必要时把 contact/ground alignment 从 ankle/calf 扩展到 toe/foot_end。
- 版本管理：当前准备提交一个已验证修复 commit，范围包括 v3 正常化、FK double-offset 修复、手臂 orientation override 和文档/测试门禁；PNS 腿部问题作为后续 commit 单独处理。

## 2026-06-26：撤回 root orientation override，改为 PNS foot-frame orientation 语义修复

- 用户复查后反馈：`2c0c1f6` 的 root/Hips orientation override 让 PNS 和 v3 的腿都变差，小腿和脚尖朝向不对。
- 已执行 `git revert 2c0c1f6`，撤回 root orientation override 方案；重新生成 PNS/v3 标准输出，v3 回到此前确认正常的链路。
- 重新对照 `soma-retargeter`：
  - PNS mapping 只到 `LeftFoot/RightFoot`，没有命名 toe；soma 把 `LeftFoot/RightFoot` 作为足部旋转目标，而不是用小腿方向代替足部方向。
  - `robot_retargeter` 当前 `left_calf/right_calf` keypoint 实际约束的是 G1 的 `left/right_ankle_roll_link`。视觉上的脚尖方向由 ankle/foot body orientation 决定。
- 根因：
  - `human_replay.py` 之前给 `left_calf/right_calf` 生成 quaternion 时只使用 robot rest link 向量和 BVH knee->ankle 目标向量。
  - 这能约束小腿段方向，但丢掉了 PNS `LeftFoot/RightFoot -> End Site` 的脚掌前向信息，导致转身时脚尖和小腿以下朝向异常。
- 修复：
  - 新增 `FOOT_ORIENTATION_KEYPOINTS_BY_FORMAT`，仅 PNS 使用。
  - PNS 的 `left_calf/right_calf` position 仍来自 knee->ankle 位置链；quaternion 改为由 semantic `left_foot/right_foot` orientation 经过 robot `key_frame_config` 转换得到。
  - 用户复查发现直接使用 PNS foot quaternion 后脚尖仍朝上。继续做 local offset 隔离后，PNS foot frame 到 G1 ankle frame 需要额外 local Y `+90deg` 校准；该校准只应用到 PNS 的 `left_calf/right_calf` orientation，不应用到 v3。
  - v3 不启用该 override，保持用户已确认正常的腿部链路。
  - 未新增或恢复任何 PNS 腿部 IK cost 特判。
- PNS 数值验证（`pick_up2274_chr00`，1835 帧，200 帧抽样，local Y `+90deg` 后）：
  - robot pelvis-local 踝间距：`min=0.0450, mean=0.3434, max=0.6406`，抽样交叉 `0/200`。
  - robot toe vector pelvis-local：`xmean=0.0362, zmean=-0.0290, zmax=0.1110`。
  - robot foot-end vector pelvis-local：`xmean=-0.0234, zmean=-0.0226, zmax=0.0359`。
- v3 回归（`Hand-Reaching-62-pangyiming-v3-1-pangyiming-v3`，208 帧，200 帧抽样）：
  - robot pelvis-local 踝间距：`min=0.2185, mean=0.2200, max=0.2211`，抽样交叉 `0/200`。
  - robot toe vector pelvis-local：`xmean=0.1152, zmean=-0.0202, zmax=0.0435`。
  - robot foot-end vector pelvis-local：`xmean=-0.0451, zmean=-0.0317, zmax=-0.0169`。
- 测试：
  - `/home/lab/miniconda3/envs/robot_retargeter/bin/python -m py_compile scripts/human_adapters/*.py scripts/human_replay.py scripts/robot_retarget.py`：通过。
  - `/home/lab/miniconda3/envs/robot_retargeter/bin/python -m unittest tests.test_human_adapters_phase2 tests.test_human_adapters_phase3 tests.test_human_replay_phase4`：通过，12 个测试。
- 当前状态：等待用户可视化复查 PNS `pick_up2274_chr00` 和 v3 回归；未把 followup 标记为 PASSED。

## 2026-06-26：PNS foot-frame local offset 候选版重跑

- 用户继续反馈：v3 `Hand-Reaching-62-pangyiming-v3-1-pangyiming-v3` 脚已正常，但 PNS `pick_up2274_chr00` 大腿以下 global rotation 仍异常，脚尖看起来朝上。
- 本轮没有恢复 root orientation override，也没有新增 PNS IK cost 特判；继续按 soma 语义使用 `LeftFoot/RightFoot` 足部旋转目标，并只在 PNS foot frame 到 G1 ankle frame 之间增加固定 local offset。
- 代码状态：
  - `FOOT_ORIENTATION_KEYPOINTS_BY_FORMAT["pns"]` 将 `left_calf/right_calf` 的 quaternion 来源绑定到 semantic `left_foot/right_foot`。
  - PNS foot frame -> G1 ankle frame 固定校准为 local Y `+90deg`。
  - v3 不启用该 foot orientation override，保持已确认正常的几何 orientation 链路。
- 重生成标准输出：
  - PNS keypoints：`scripts/human_replay.py --format pns --input-bvh /home/lab/Downloads/pick_up/pick_up2274_chr00.bvh --robot-config config/robot/g1.yaml --skeleton-config config/skeleton/skeleton.yaml --output-dir output_data/keypoints/g1 --no-viewer`
  - PNS retarget：`scripts/robot_retarget.py --config config/robot/g1.yaml --keypoints-name pick_up2274_chr00 --no-render-debug`
  - v3 keypoints：`scripts/human_replay.py --format v3 --input-bvh /home/lab/Desktop/soma-retargeter/assets/motions/v3_test/bvh/Hand-Reaching-62-pangyiming-v3-1-pangyiming-v3.bvh --robot-config config/robot/g1.yaml --skeleton-config config/skeleton/skeleton.yaml --output-dir output_data/keypoints/g1 --no-viewer`
  - v3 retarget：`scripts/robot_retarget.py --config config/robot/g1.yaml --keypoints-name Hand-Reaching-62-pangyiming-v3-1-pangyiming-v3 --no-render-debug`
- 输出：
  - `output_data/robot_motion/pick_up2274_chr00_g1.csv`，shape `(1835, 36)`。
  - `output_data/robot_motion/Hand-Reaching-62-pangyiming-v3-1-pangyiming-v3_g1.csv`，shape `(208, 36)`。
- MuJoCo FK 抽样指标（200 帧）：
  - PNS `pick_up2274_chr00`：pelvis-local ankle sep `min=0.0450, mean=0.3434, max=0.6406`，ankle cross `0/200`；toe-from-ankle pelvis-local `xmean=0.0362, zmean=-0.0290, zmax=0.1042`；foot-end pelvis-local `xmean=-0.0234, zmean=-0.0226, zmax=0.0277`。
  - v3 `Hand-Reaching-62...`：pelvis-local ankle sep `min=0.2185, mean=0.2200, max=0.2211`，ankle cross `0/200`；toe-from-ankle pelvis-local `xmean=0.1152, zmean=-0.0202, zmax=0.0417`；foot-end pelvis-local `xmean=-0.0451, zmean=-0.0317, zmax=-0.0174`。
- 测试：
  - `/home/lab/miniconda3/envs/robot_retargeter/bin/python -m py_compile scripts/human_adapters/*.py scripts/human_replay.py scripts/robot_retarget.py`：通过。
  - `/home/lab/miniconda3/envs/robot_retargeter/bin/python -m unittest tests.test_human_adapters_phase2 tests.test_human_adapters_phase3 tests.test_human_replay_phase4`：通过，13 个测试。
- 当前判断：
  - 当前 PNS 候选版的 toe/foot_end 竖直均值已经向下，不再是整体脚尖朝上；但 PNS 仍有少数帧 toe 向量接近或略高于水平面，需要用户可视化复查后才能把 followup 标记为 PASSED。
