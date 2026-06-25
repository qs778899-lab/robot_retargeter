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
- 单位判定测试：对 fixture 或样例 BVH 输出 `raw_height`、`unit_scale`、判定依据；cm 级数据必须转换到米级 keypoints。
- 朝向判定测试：输出 `up_axis`、`lateral_axis`、`forward_axis`，并验证 adapter 输出统一为 Z-up、X-forward、Y-left。
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
  - 左右手脚未镜像反转。
  - PNS synthetic toe/contact 点不导致 contact 逻辑异常。
