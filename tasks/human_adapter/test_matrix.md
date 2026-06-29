# Test Matrix

所有测试都是阶段门禁。当前阶段任意一项失败，都必须停留在当前阶段，修复后重跑该阶段全部测试；不能进入下一阶段。

## phase_1：文档与接口定稿

- 检查 `tasks/human_adapter/plan.md` 存在，并包含：
  - PNS 参考链路说明
  - v3 BVH 侧参考链路说明
  - `robot_retargeter` 当前 keypoints pkl schema
  - 分阶段实施计划
- 检查计划明确本任务不适配 FBX、不扫描 FBX、不引入 Blender。
- 检查 `status.md`、`test_matrix.md`、`log.md` 存在。
- 检查 `plan.md` 明确写出阶段门禁规则：测试未通过不能进入下一阶段。

## phase_2：基础 BVH adapter 与 mapping

- `python -m py_compile scripts/human_adapters/*.py`
- mapping load 单元测试：`config/human_mappings/pns.json` 和 `config/human_mappings/v3.json` 能加载并通过 required joints 校验。
- 最小 BVH fixture FK 测试：frame count、fps、root position、wxyz quaternion shape 正确。
- 非 root position channel FK 测试：有 `X/Y/Zposition` 的非 root joint 不能再额外叠加 `OFFSET`，避免骨长和 raw height 翻倍。
- 单位判定测试：对 fixture 或样例 BVH 输出 `raw_height`、`unit_scale`、判定依据；cm 级数据必须转换到米级 keypoints。
- 朝向判定测试：输出 `up_axis`、`lateral_axis`、`forward_axis`，并验证 adapter 输出统一为 Z-up、X-forward、Y-left。
- 自动轴变换测试：覆盖非标准 Maya 数据，例如 `up=+y, forward=+x, lateral=-z` 的 v3 BVH，必须映射为 MuJoCo `+Z/+X/+Y`，不能固定套用 Maya 矩阵。
- 坐标变换测试：position 和 quaternion 同步变换；同一骨架在转换后 head 高于 feet，foot-to-toe/End Site 主要沿 X 轴。

## phase_3：PNS/v3 discovery 与 semantic skeleton

- PNS discovery 能扫描 task/input-dir/input-bvh，且跳过 `_soma`、`_trimmed`、`_tpose`、`_armtwist`。
- v3 discovery 能扫描 task/input-dir/input-bvh；可解析 `<base>-<person>.bvh` 作为 metadata，但不查找 FBX。
- semantic skeleton 输出 shape：
  - positions: `[T, len(REPLAY_BODY_NAMES), 3]`
  - quaternions: `[T, len(REPLAY_BODY_NAMES), 4]`
- PNS foot End Site 能生成 synthetic `left_toe/right_toe`；End Site 缺失时输出 warning 并降级到 foot。
- head 优先直接映射 `Head`；真正缺失时输出 warning 并外推，不影响躯干/四肢/脚接触。

## phase_4：human_replay.py 入口与 keypoints pkl

- `python scripts/human_replay.py --help`
- 单 BVH no-viewer smoke 生成 `output_data/keypoints/<robot>/<motion>_keypoints.pkl`。
- pkl 字段校验：
  - `keypoint_names`
  - `positions`
  - `quaternions`
  - `fps`
  - `contact_names`
  - `contact_states`
- pkl shape 与 `scripts/robot_retarget.py` 读取逻辑兼容。
- pkl 或生成日志包含单位和朝向 debug 信息：`raw_height`、`unit_scale`、`up_axis`、`lateral_axis`、`forward_axis`、root/head/foot/toe axis range。
- pkl 或生成日志包含地面对齐 debug 信息：`ground_links`、`observed_ground_z`、`target_ground_z`、`z_shift`。
- pkl 支撑点高度门禁：生成后 `left_calf/right_calf` 最低 Z 应接近目标机器人对应踝端高度，不能保留 1m 级 BVH root/world offset。
- human BVH pkl 必须携带 `ik_orientation_cost_scales`，手臂相关 keypoint 的 orientation scale 默认为 `0.0`，避免 BVH 手臂 roll 与目标机器人自由度冲突。

## phase_5：端到端 smoke 与可视化检查

- PNS 样例：
  - `human_replay.py` 生成 keypoints pkl。
  - `robot_retarget.py --no-render-debug` 生成目标机器人 CSV。
- v3 样例：
  - `human_replay.py` 生成 keypoints pkl。
  - `robot_retarget.py --no-render-debug` 生成目标机器人 CSV。
- 检查输出 CSV 行数等于有效帧数，或差异有明确解释。
- 可选可视化检查：
  - 角色未躺倒或侧身。
  - 机器人足端在地面附近，不应整体悬空。
  - 左右手脚未镜像反转。
  - 手臂目标左右关系正确：左臂主要在 MuJoCo +Y，右臂主要在 -Y；若肘部向身体中线凹陷，必须检查 lateral/forward 轴和 shoulder mapping。
  - 若手臂位置目标合理但 robot 手臂仍内凹，必须做一次关闭手臂 orientation cost 的隔离实验；位置误差显著下降时，应保留手臂位置约束并关闭/降低手臂 orientation cost。
  - PNS synthetic toe/contact 点不导致 contact 逻辑异常。

## followup_pns_leg：PNS 转身腿部异常回归门禁

- PNS 完整动作 `pick_up2274_chr00` 必须单独执行 keypoints 与 robot motion 数值诊断。
- 必须同时记录：
  - keypoints 全局左右脚交叉帧数。
  - robot 输出全局左右脚交叉帧数。
  - 以 pelvis/root facing 为基准的局部左右脚交叉帧数。
  - sampled foot/toe Z min/mean/max。
  - `left_hip/right_hip/left_calf/right_calf` position/rotation error。
- 若 robot 交叉脚与 keypoints 全局交叉一致，不能只调 IK 权重；必须先解释 keypoints 是否需要按 root/facing 局部化或修正足端目标。
- BVH 足部 orientation 门禁：`left_calf/right_calf` 对应 robot `ankle_roll_link`，其 quaternion 不能只由 knee->ankle 小腿向量决定，也不能只用 source foot quaternion 加固定 offset。PNS/v3 都应从几何构造 ankle frame：`+Z = ankle -> knee`，`+X = foot -> toe/End Site` 投影到垂直于 `+Z` 的平面，`+Y` 由右手系得到。修改该逻辑必须同时重跑 PNS/v3 数值门禁与可视化回归。
- 修复后必须重新可视化 PNS `pick_up2274_chr00`，并记录用户或截图验证结果。
