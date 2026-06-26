# Human Adapter 接入计划：PNS 与 v3 BVH 人体骨架格式

## 目标

在 `robot_retargeter` 中接入 `/home/lab/Desktop/soma-retargeter` 已使用的两类人体 BVH 骨架命名格式：

- `tools/mappings/pns.json`：PNS/PNL 类纯 BVH 骨架，用于 `batch_retarget_bvh.py --mapping tools/mappings/pns.json`。
- `tools/mappings/v3.json`：v3 人体 BVH 骨架命名，用于 `batch_retarget.py --mapping tools/mappings/v3.json` 的 BVH motion 侧。

本任务只考虑 BVH 文件适配，不考虑 FBX 文件适配、FBX T-pose 抽取、Blender 依赖或 BVH-FBX 配对校验。

接入方式：

```text
PNS/v3 BVH
  -> BVH parser + FK
  -> human skeleton mapping
  -> robot_retargeter 标准语义骨架
  -> 复用现有 keypoints pkl 生成逻辑
  -> 复用 scripts/robot_retarget.py 做目标机器人 IK
```

核心原则：

- 新格式逻辑放在 adapter 层，不修改 `scripts/robot_retarget.py` 的 IK 核心。
- `robot_retargeter` 的核心输入仍是 keypoints pkl，不直接让 IK 核心读取 BVH。
- PNS 与 v3 的差异集中在关节名 mapping、缺失关节处理和 task/input discovery 中。
- 不迁移 `soma-retargeter` 的 SOMA scaler、G1 CSV、motion_lib PKL 链路。

## 参考仓库链路理解

### PNS：`batch_retarget_bvh.py` + `pns.json`

参考命令：

```bash
python tools/batch_retarget_bvh.py \
  --task pick_up \
  --mapping tools/mappings/pns.json \
  --strip-dead-frames \
  --config-version v6 \
  --save-preview \
  --error-log \
  --pkl-version-suffix
```

参考仓库处理链路：

1. `BvhFolderAdapter(task, repo_root).discover()` 扫描 `assets/motions/bvh/<task>/*.bvh`。
2. 跳过 `_soma`、`_trimmed`、`_tpose`、`_armtwist` 等中间文件。
3. 使用 task 级 BVH T-pose 或第一个 motion BVH frame 0 生成 SOMA scaler。
4. `remap_bvh.py --mapping pns.json` 将源 BVH 关节名重命名为 SOMA 语义名。
5. 可选 `bvh_strip_dead_frames.py` 裁剪前后 dead frames。
6. `retarget_bvh.py` 做 SOMA/G1 IK，输出 CSV、preview CSV、error log。
7. 可选转换为 motion_lib PKL。

对 `robot_retargeter` 的可复用结论：

- 可复用 PNS 的 task/file discovery 思路。
- 可复用“mapping JSON 描述外部关节名到内部语义名”的边界。
- 不复用 SOMA scaler 和 `retarget_bvh.py`，因为目标仓库已有 keypoints -> robot IK 流程。

`pns.json` 格式特征：

- 源骨架是 Maya/MotionBuilder 风格 BVH，约 59 个关节，含手指，但主流程只需要躯干、四肢主链。
- 映射到 SOMA 的主关节包括：`Hips`、`Chest`、`Neck1`、双臂三段、双腿三段。
- 没有命名 toe joint，但 `LeftFoot` / `RightFoot` 下有 BVH `End Site`。以 `pick_up/pick__up745_chr00.bvh` 为例，脚部 End Site offset 是 `0, -10, 15.12`，语义上更接近脚尖/脚底末端点，adapter 应解析并暴露为 synthetic toe/contact 点。
- 有命名 `Head` joint；原 `pns.json` 没映射 `Head` 是因为 SOMA/G1 链路未使用它，不代表 BVH 缺失头部。
- 关键映射：
  - `Hips -> Hips`
  - `Spine2 -> Chest`
  - `Neck1 -> Neck1`
  - `LeftArm/LeftForeArm/LeftHand`
  - `RightArm/RightForeArm/RightHand`
  - `LeftUpLeg/LeftLeg/LeftFoot/LeftFoot End Site`
  - `RightUpLeg/RightLeg/RightFoot/RightFoot End Site`
  - `Head`

### v3：`batch_retarget.py` + `v3.json` 的 BVH 侧

参考命令：

```bash
python tools/batch_retarget.py \
  --task Hand-Reaching-658 \
  --mapping tools/mappings/v3.json \
  --strip-dead-frames \
  --config-version v6 \
  --retarget-version v6 \
  --save-preview \
  --error-log
```

本计划只吸收其中 BVH motion 侧的处理方式：

1. 扫描 task 下的 BVH 文件。
2. 可按 `<base>-<person>.bvh` 解析 motion stem，用于输出命名和日志展示。
3. 使用 BVH 自身 HIERARCHY/OFFSET 和 MOTION channels 做 FK。
4. 使用 `v3.json` 的关节名映射转换到目标仓库内部语义骨架。
5. 可选 dead-frame 裁剪。

不纳入范围：

- 不扫描或读取 FBX。
- 不用 FBX frame 0 生成 T-pose。
- 不做 FBX-vs-BVH skeleton consistency check。
- 不引入 Blender。

`v3.json` 格式特征：

- BVH 关节命名以 `Hips` 为 root。
- 躯干使用 `Spine3 -> Chest`，不同数据可能需要兼容 `Spine4` alias。
- `Neck -> Neck1`。
- 双腿包含 toe：
  - `LeftUpLeg/LeftLeg/LeftFoot/LeftToeBase`
  - `RightUpLeg/RightLeg/RightFoot/RightToeBase`
- 双臂三段：
  - `LeftArm/LeftForeArm/LeftHand`
  - `RightArm/RightForeArm/RightHand`

## `robot_retargeter` 当前数据流

当前仓库不直接以 BVH 作为 IK 输入，而是先生成标准 keypoints pkl：

1. `scripts/smpl_replay.py`
   - 从 SMPL-X `.npz` 生成人体语义骨架位置与四元数。
   - 使用 `config/skeleton/skeleton.yaml` 的 `skeleton_links` 和目标 `config/robot/<robot>.yaml` 的 `robot_links` 做 link scaling。
   - 写出 `output_data/keypoints/<robot>/<motion>_keypoints.pkl`。

2. `scripts/robot_replay.py`
   - 从源机器人 qpos CSV 生成同样的语义骨架 keypoints。
   - 再按目标机器人 link scaling 写出 keypoints pkl。

3. `scripts/robot_retarget.py`
   - 读取 keypoints pkl。
   - 根据机器人 YAML 的 `ik_match_table` 做 mink IK，输出机器人 motion CSV。

`scripts/robot_retarget.py` 读取的 pkl 必需字段：

```text
keypoint_names
positions      # [T, K, 3], float32
quaternions    # [T, K, 4], wxyz, float32
contact_states
```

常用可选字段：

```text
fps
contact_names
```

当前标准语义骨架名来自 `scripts/smpl_replay.py::REPLAY_BODY_NAMES`：

```text
hips, left_up_leg, left_leg, left_foot, left_toe,
right_up_leg, right_leg, right_foot, right_toe,
spine1, spine2, chest, neck, head,
left_shoulder, left_arm, left_fore_arm, left_hand,
right_shoulder, right_arm, right_fore_arm, right_hand,
hips_mean, shoulder_mean
```

因此 PNS/v3 BVH 的接入点应在 `smpl_replay.py` 之前：把 BVH FK 结果转换成上述语义骨架，再复用现有 `build_retarget_keypoints()`、contact 计算和 `save_keypoints_pkl()`。

## 目标架构

建议新增轻量 adapter 层：

```text
scripts/
  human_adapters/
    __init__.py
    base.py         # SourceMotion / HumanMotionSemantic / common validation
    bvh_parser.py   # BVH hierarchy + motion channels + FK
    mappings.py     # mapping schema load/validate，PNS/v3 aliases
    pns.py          # PNS BVH file/task discovery
    v3.py           # v3 BVH file/task discovery
    keypoints.py    # semantic skeleton -> keypoints pkl helper

config/
  human_mappings/
    pns.json
    v3.json

scripts/
  human_replay.py   # 新入口：BVH -> keypoints pkl
```

职责边界：

- `human_adapters/*` 只处理 BVH 输入格式、FK、关节名映射、坐标系转换。
- `human_replay.py` 只编排 adapter、标准 keypoints 构造、输出路径。
- `robot_retarget.py` 不因 PNS/v3 做格式私有修改。
- `config/human_mappings/*.json` 维护外部骨架名到内部语义骨架名的映射。

## 标准中间表示设计

adapter 输出统一结构：

```python
HumanMotionSemantic(
    positions: np.ndarray,     # [T, len(REPLAY_BODY_NAMES), 3], meter, Z-up, X-forward
    quaternions: np.ndarray,   # [T, len(REPLAY_BODY_NAMES), 4], wxyz
    fps: float,
    source_name: str,
    source_format: str,        # "pns_bvh" / "v3_bvh"
    missing_joints: list[str],
)
```

内部语义骨架填充规则：

- `hips` 使用源 `Hips`。
- `hips_mean` 优先取 `left_up_leg` 与 `right_up_leg` 平均；若缺失则 fallback 到 `hips`。
- `shoulder_mean` 取 `left_arm` 与 `right_arm` 平均；若缺失则 fallback 到 `chest`。
- `spine1` / `spine2` 对 PNS/v3 不一定直接存在，可在 `hips -> chest` 上插值生成。
- `chest`：
  - PNS: `Spine2`
  - v3: `Spine3`，必要时兼容 `Spine4`
- `neck`：
  - PNS: `Neck1`
  - v3: `Neck`
- `head` 优先使用源 BVH 命名 `Head`；如果某个格式确实缺失，再使用 `neck` 沿 `chest -> neck` 方向外推并记录 warning。
- 腿：
  - `LeftUpLeg -> left_up_leg`
  - `LeftLeg -> left_leg`
  - `LeftFoot -> left_foot`
  - 右腿同理
- toe：
  - v3 使用命名 `LeftToeBase` / `RightToeBase`。
  - PNS 使用 `LeftFoot` / `RightFoot` 的 BVH `End Site` 生成 synthetic `left_toe/right_toe`。
  - 如果某条 BVH 没有 foot End Site，再降级为 foot 近似并记录 warning。

四元数策略：

- 按 BVH `CHANNELS` 声明顺序组合 local Euler rotation，做 FK 得到各 joint world quaternion。
- 输出统一为 wxyz。
- 派生点策略：
  - `hips_mean` 使用左右髋四元数平均，缺失时用 `hips`。
  - `shoulder_mean` 使用左右肩/上臂四元数平均，缺失时用 `chest`。
  - 插值 spine 可先用相邻父节点四元数，后续再升级为 slerp。
- 继续复用机器人 YAML 的 `key_frame_config` 做轴映射和局部 offset。

坐标系策略：

- 先按项目级 `AGENTS.md` 触发规则读取 `docs/human_bvh_intake.md`，实证判定 up/lateral/forward；不能只靠格式名假设。
- PNS/v3 BVH 初始假设按 Maya/MotionBuilder 风格处理：Y-up、+Z forward，但必须通过 Head-Foot、Left-Right、foot-to-toe/End Site 统计确认。
- `robot_retargeter` 内部保持 MuJoCo 风格：Z-up、+X forward。
- adapter 边界做显式轴变换，并在 `human_replay.py` 提供：
  - `--facing-direction Maya|Mujoco`
  - 默认 `Maya`
- 坐标变换必须同时作用于 positions 和 quaternions。

单位策略：

- 先按 `docs/human_bvh_intake.md` 的单位规则计算原始 BVH 身高并记录 `raw_height`、`unit_scale`、判定依据。
- PNS 样例 `pick_up/pick__up745_chr00.bvh` 的 Hips 高度约 `97.12`，腿段 offset 约 `45 + 42`，整体量级更像厘米；该类数据接入时应重点验证是否需要 `--unit-scale 0.01`。
- 提供 `--unit-scale`，默认可以是 `auto` 或显式数值；若使用 `auto`，必须打印判定结果，不能静默转换。
- 如果源 BVH 身高明显大于合理人体米制范围，例如 > 10，可提示或自动选择 `unit_scale=0.01`，但必须记录到日志。

## PNS BVH 接入计划

输入发现：

- `--format pns`
- `--task <name>`：扫描 `dataset/human_bvh/pns/<task>/*.bvh`
- `--input-dir <dir>`：扫描目录下 BVH
- `--input-bvh <file>`：单文件
- 跳过 `_soma`、`_trimmed`、`_tpose`、`_armtwist`

mapping 初版：

```json
{
  "Hips": "hips",
  "Spine2": "chest",
  "Neck1": "neck",
  "LeftArm": "left_arm",
  "LeftForeArm": "left_fore_arm",
  "LeftHand": "left_hand",
  "RightArm": "right_arm",
  "RightForeArm": "right_fore_arm",
  "RightHand": "right_hand",
  "LeftUpLeg": "left_up_leg",
  "LeftLeg": "left_leg",
  "LeftFoot": "left_foot",
  "LeftFoot_EndSite": "left_toe",
  "RightUpLeg": "right_up_leg",
  "RightLeg": "right_leg",
  "RightFoot": "right_foot",
  "RightFoot_EndSite": "right_toe",
  "Head": "head"
}
```

注意事项：

- PNS 没有命名 toe joint，但有 foot End Site；应把 End Site 纳入 BVH parser 的输出，而不是忽略 toe。
- `contact_names` 可以使用 synthetic `left_toe/right_toe` 提升脚接触判断；若 End Site 缺失再用 `left_foot/right_foot` 近似。
- `--strip-dead-frames` 可按 root translation、root rotation 和主链 joint rotation 是否长时间全零裁剪。

## v3 BVH 接入计划

输入发现：

- `--format v3`
- `--task <name>`：扫描 `dataset/human_bvh/v3/<task>/*.bvh`
- `--input-dir <dir>`：扫描目录下 BVH
- `--input-bvh <file>`：单文件
- 可解析 `<base>-<person>.bvh` 作为 metadata，但不查找 FBX。
- 跳过 `_soma`、`_trimmed`、`_tpose`、`_armtwist`

mapping 初版：

```json
{
  "Hips": "hips",
  "Spine3": "chest",
  "Neck": "neck",
  "LeftArm": "left_arm",
  "LeftForeArm": "left_fore_arm",
  "LeftHand": "left_hand",
  "RightArm": "right_arm",
  "RightForeArm": "right_fore_arm",
  "RightHand": "right_hand",
  "LeftUpLeg": "left_up_leg",
  "LeftLeg": "left_leg",
  "LeftFoot": "left_foot",
  "LeftToeBase": "left_toe",
  "RightUpLeg": "right_up_leg",
  "RightLeg": "right_leg",
  "RightFoot": "right_foot",
  "RightToeBase": "right_toe"
}
```

注意事项：

- v3 有 toe，可比 PNS 更可靠地计算 foot contact。
- 若样例 BVH 使用 `Spine4` 作为 chest 分支，mapping loader 支持 alias：
  - 主 mapping: `Spine3 -> chest`
  - fallback alias: `Spine4 -> chest`
- alias 放在 mapping/adapter 层，不写进 FK parser。

## 新入口建议

单文件：

```bash
python scripts/human_replay.py \
  --format pns \
  --input-bvh dataset/human_bvh/pns/pick_up/example.bvh \
  --robot-config config/robot/g1.yaml \
  --skeleton-config config/skeleton/skeleton.yaml \
  --mapping config/human_mappings/pns.json \
  --strip-dead-frames \
  --no-viewer
```

批量：

```bash
python scripts/human_replay.py \
  --format v3 \
  --task Hand-Reaching-658 \
  --input-root dataset/human_bvh/v3 \
  --robot-config config/robot/g1.yaml \
  --mapping config/human_mappings/v3.json \
  --strip-dead-frames \
  --no-viewer
```

输出：

```text
output_data/keypoints/<robot>/<motion_stem>_keypoints.pkl
```

后续沿用：

```bash
python scripts/robot_retarget.py \
  --config config/robot/g1.yaml \
  --keypoints-name <motion_stem> \
  --no-render-debug
```

实现上优先复用 `smpl_replay.py` 中的稳定函数：

- `build_retarget_keypoints`
- `compute_contact_sequence`
- `append_robot_foot_keypoints`
- `scale_keypoint_frame_displacements`
- `offset_keypoints_by_contact_height`
- `save_keypoints_pkl`

## 分阶段实施计划

### 阶段门禁规则

每个 phase 都必须严格执行 `tasks/human_adapter/test_matrix.md` 中对应章节的全部测试。执行规则：

1. 开始任何 phase 前，先读取 `tasks/human_adapter/status.md`，只执行 `current_phase`。
2. 当前 phase 的实现完成后，运行 `test_matrix.md` 中该 phase 的全部测试。
3. 只有全部测试通过，才能在 `status.md` 中把该 phase 标记为 `PASSED`，并把 `current_phase` 推进到下一阶段。
4. 任何测试失败时，必须停留在当前 phase，修复后重跑同一批测试；不能跳到下一阶段。
5. 测试结果、失败原因和修复结论必须追加到 `tasks/human_adapter/log.md`。

### Phase 1：文档与接口定稿

产物：

- 本计划文档。
- `status.md`、`test_matrix.md`、`log.md`。
- 明确只做 BVH 适配，不做 FBX 适配。

验收：

- 文档能让后续实现直接按 BVH adapter 开始编码。
- 明确 PNS/v3 的输入发现规则、mapping、标准中间表示和输出 pkl schema。
- 必须通过 `test_matrix.md#phase_1` 的全部检查，才能进入 Phase 2。

### Phase 2：基础 BVH parser 与 mapping

产物：

- `scripts/human_adapters/base.py`
- `scripts/human_adapters/bvh_parser.py`
- `scripts/human_adapters/mappings.py`
- `config/human_mappings/pns.json`
- `config/human_mappings/v3.json`

实现重点：

- 解析 BVH hierarchy、OFFSET、CHANNELS、MOTION frame time。
- 支持 BVH FK，输出世界 position 和 wxyz quaternion。
- 支持 Maya -> MuJoCo 坐标变换。
- mapping 校验：缺 root、缺双腿、缺双臂时 fail；PNS foot End Site 缺失或 head 缺失时 warn 并降级。

测试门禁：

- 必须通过 `test_matrix.md#phase_2` 的全部测试，才能进入 Phase 3。

### Phase 3：PNS/v3 BVH discovery 与 semantic skeleton

产物：

- `scripts/human_adapters/pns.py`
- `scripts/human_adapters/v3.py`
- `scripts/human_adapters/keypoints.py`

实现重点：

- PNS task/input-dir/input-bvh discovery。
- v3 task/input-dir/input-bvh discovery。
- 源 BVH FK 结果转 `REPLAY_BODY_NAMES` 语义骨架。
- 派生 `hips_mean`、`shoulder_mean`、`spine1`、`spine2`，并支持 PNS foot End Site -> toe。

测试门禁：

- 必须通过 `test_matrix.md#phase_3` 的全部测试，才能进入 Phase 4。

### Phase 4：`human_replay.py` 入口接入 keypoints pkl

产物：

- `scripts/human_replay.py`
- 可选 `bash/retarget_from_human_bvh.sh`

实现重点：

- 单 BVH 和 task 批量两种模式。
- 复用 `build_retarget_keypoints()` 和 `save_keypoints_pkl()`。
- `--strip-dead-frames`、`--fps auto|value`、`--facing-direction`、`--unit-scale`。
- 输出到 `output_data/keypoints/<robot>/`。

测试门禁：

- 必须通过 `test_matrix.md#phase_4` 的全部测试，才能进入 Phase 5。

### Phase 5：端到端 smoke 与可视化检查

产物：

- PNS 一条样例 BVH 生成 keypoints pkl。
- v3 一条样例 BVH 生成 keypoints pkl。
- 至少一个目标机器人 retarget CSV。
- 记录关键指标：frames、fps、keypoint shape、IK 输出 CSV 行数、warning。

测试门禁：

- 必须通过 `test_matrix.md#phase_5` 的全部测试，才能把任务标记为 COMPLETE。

## 风险与处理

- 坐标系错误：adapter 边界同时转换 position 和 quaternion；增加 root/head/foot axis range debug 输出。
  - 避免方法：
    - 坐标变换只允许在 BVH adapter 边界做一次，后续 semantic skeleton、keypoints pkl、`robot_retarget.py` 都只处理统一的 MuJoCo 约定：Z-up、X-forward。
    - 变换矩阵集中定义，例如 `MAYA_TO_MUJOCO = [[0, 0, 1], [1, 0, 0], [0, 1, 0]]`，不要在多个函数里手写轴交换。
    - positions 使用 `p_mujoco = R_axis @ p_source`；quaternion 必须同步做基变换，使用 `R_mujoco = R_axis @ R_source @ R_axis.T` 后再转回 wxyz quaternion，不能只换 position。
    - `--facing-direction` 默认 `Maya`，但入口必须允许 `Mujoco` 直通；生成 keypoints pkl 时把 `source_coordinate`、`axis_transform` 写入 debug metadata 或日志。
    - 单位缩放必须在坐标变换前后保持一致，建议顺序为：BVH FK 原坐标 -> unit scale -> axis transform -> semantic skeleton。
  - 接入时的静态检查：
    - frame 0 或前 N 帧中，`head.z - min(left_foot.z, right_foot.z)` 应接近人体身高，且为正。
    - `left_up_leg - right_up_leg` 的最大分量应主要落在 MuJoCo Y 轴；若主要落在 X/Z，说明 lateral 轴可能错。
    - `left_toe/right_toe` 或 foot End Site 相对 foot 的水平前向偏移应主要落在 MuJoCo X 轴；若主要落在 Y，说明 forward 轴可能错。
    - root/head/foot 的 `min/max/range` 必须打印到 debug 日志，字段至少包括 `root_xyz_range`、`head_minus_feet_mean`、`left_right_hip_delta_mean`、`foot_to_toe_delta_mean`。
  - 出现问题的判定：
    - 人整体躺倒：up 轴错，通常表现为 `head.z` 不明显高于 foot，或人体高度落在 X/Y range。
    - 人侧身站立或整体旋转 90 度：forward/lateral 轴错，通常 foot-to-toe 偏移不在 X 轴。
    - 左右镜像：lateral 轴符号错，通常 `left_up_leg.y` 小于 `right_up_leg.y`，或左右手脚交换。
    - retarget 后全身 IK 误差都大：优先查坐标系；如果只有局部肢体异常，再查 mapping 或 BVH rotation order。
  - 排查流程：
    1. 对同一 BVH 分别用 `--facing-direction Maya` 和 `--facing-direction Mujoco` 生成只包含前 30 帧的 debug keypoints。
    2. 比较 debug 统计：选 `head_minus_feet_mean` 为正且最大、foot-to-toe 主要沿 +X、左右髋主要沿 Y 的结果。
    3. 用 keypoints viewer 或 `human_replay.py --viewer` 查看 root、head、feet、toe 点，不先跑机器人 IK。
    4. 再跑 `robot_retarget.py --no-render-debug`，若 CSV 正常生成但姿态整体错，回到 adapter 坐标变换；若只有膝/肘/腕异常，再查 mapping 和 quaternion 局部轴。
- BVH rotation order 错误：必须按 BVH `CHANNELS` 声明顺序组合旋转，不能假设固定 XYZ。
- 单位错误：提供 `--unit-scale`，打印源 skeleton 身高范围。
- PNS toe 不是命名 joint，而是 foot End Site：BVH parser 需要保留 End Site 世界坐标，并映射为 synthetic `left_toe/right_toe`；只有 End Site 缺失时才用 foot 近似。
- v3 spine 命名差异：mapping 支持 alias，不在 FK parser 硬编码。
- head 缺失：PNS 样例实际有 `Head` joint，应直接映射；真正缺失时只影响 head orientation/position IK target，躯干、四肢和脚接触不应受影响，可从 neck/chest 外推并记录 warning。

## 不在本任务范围内

- 不适配 FBX。
- 不扫描或读取 FBX 文件。
- 不引入 Blender。
- 不做 BVH-FBX 骨架一致性校验。
- 不迁移 `soma-retargeter` 的 SOMA scaler、`retarget_bvh.py` 或 motion_lib PKL。
- 不把 PNS/v3 格式逻辑写进 `scripts/robot_retarget.py`。
