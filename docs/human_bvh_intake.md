# Human BVH Intake Rules

本文是 human motion BVH 接入、BVH adapter、BVH retarget 任务的专项规则。只有处理 BVH 输入时需要读取；非 BVH 任务不需要加载本文件。

## 必查项

处理任何新的 human motion BVH 时，必须先实证确认：

- 数值单位：米、厘米、毫米，或其他比例。
- 人体骨架朝向：up/lateral/forward 轴和正方向。
- 接入边界：输出到项目内部前统一为 MuJoCo 约定，Z-up、X-forward、Y-left。

不能只根据文件名、采集系统名、数据集名或“看起来像 Maya”做假设。

## 单位判定

从 BVH HIERARCHY 的 OFFSET 和 frame 0 FK 计算人体高度，例如 `Head` 或 `Head End Site` 到左右脚、toe 或 foot End Site 的垂直距离。

典型判定：

- 身高约 `1.0 ~ 2.5`：大概率是米，`unit_scale=1.0`。
- 身高约 `80 ~ 400`：大概率是厘米，`unit_scale=0.01`。部分 BVH 的 head/foot End Site 会把 raw height 拉到 300cm 级，仍应按厘米处理。
- 身高约 `800 ~ 4000`：大概率是毫米，`unit_scale=0.001`。

要求：

- 判定结果必须记录到任务文档或日志中。
- 至少记录 `raw_height`、`unit_scale`、判定依据。
- 不允许静默猜单位；如果无法判定，必须暴露参数让用户显式指定，例如 `--unit-scale`。

## 朝向判定

必须用数据本身判定 up/lateral/forward：

- up 轴：看 `Head - Foot/Toe/Foot End Site`，绝对差最大的轴通常是 up。
- lateral 轴：看 `LeftShoulder - RightShoulder` 或 `LeftUpLeg - RightUpLeg`，绝对差最大的轴是左右轴，同时符号决定左右是否镜像。
- forward 轴：优先看 `foot -> toe` 或 `foot -> Foot End Site` 的水平偏移。
- root 位移主方向只能作为辅助，并且只适用于走、跑、跳这类水平位移动作；弯腰、下蹲、坐下、原地伸手等动作不能用 root 位移主方向判定 forward。

要求：

- 判定结果必须记录到任务文档或日志中。
- 至少记录 `up_axis`、`lateral_axis`、`forward_axis`、是否需要 `Maya -> MuJoCo` 轴变换。

## 接入边界

- BVH adapter 输出到项目内部前，必须统一到 MuJoCo 约定：Z-up、X-forward、Y-left。
- 单位缩放和坐标变换都只能在 adapter 边界做一次。
- 后续 workflow、keypoints pkl、robot retarget 不再处理源格式私有单位/朝向。
- position 和 quaternion 必须同步变换。只变 position 不变 quaternion 会导致姿态看似站立但局部旋转全错。
- debug 日志必须打印 root/head/foot/toe 的 axis range，用于快速发现躺倒、侧身、左右镜像和单位错误。
- BVH FK 处理 position channel 时不能把 `OFFSET` 和 `X/Y/Zposition` 盲目相加。若某个 joint 有 position channels，frame 数据通常已经表示该 joint 的 local translation；再加 OFFSET 会把骨长翻倍，表现为身高 300cm 级、ground shift 过大、腿/手姿态异常。
- 不同 BVH 即使同属 v3/PNS，也不能固定套同一个 Maya 矩阵。应根据实测 `forward_axis/lateral_axis/up_axis` 构造 source -> MuJoCo 矩阵：source forward 映射到 target +X，source lateral 映射到 target +Y，source up 映射到 target +Z。
- keypoints 输出前必须做地面对齐检查。至少用目标机器人左右踝端/足端对应 keypoints 的最低 Z 和机器人模型初始对应 body Z 做对齐，避免把 BVH 世界坐标 root offset 原样带入 IK，导致机器人悬空。
- 若目标机器人 keypoint 名称是 calf/ankle 但实际约束的是 ankle/foot body，orientation 不能只由 knee->ankle 小腿向量决定，也不能只信任 source foot quaternion。对 PNS/v3 这类 BVH，应从几何构造 ankle frame：`+Z = ankle -> knee`，`+X = foot -> toe/End Site` 投影到垂直于 `+Z` 的平面，`+Y` 由右手系得到；toe 可以不作为强 position target，但必须可作为 foot orientation 依据。若脚尖仍整体朝上，应用 robot FK 的 toe/foot_end 世界方向和 ankle link global rotation 验证，不要直接调 IK cost。
- 若目标机器人 keypoint 名称是 thigh/knee 但实际约束的是 knee body，orientation 不能只由 `hip -> knee` 或 `knee -> hip` 单根大腿向量决定；单向量只能确定一个轴，绕骨轴的 twist 未定义，转身时会把 hip_yaw/ankle 推到限位。对 PNS/v3 这类 BVH，应从几何构造 knee/thigh frame：`+Z = knee -> hip`，`+X = pelvis facing` 投影到垂直于 `+Z` 的平面，`+Y` 由右手系得到。
- 对 human BVH 手臂，位置目标通常比 roll/orientation 更可信。若手臂 orientation target 与目标机器人肩肘自由度冲突，应通过 keypoints payload 的 per-keypoint orientation scale 关闭或降低手臂 orientation cost，而不是牺牲 wrist/elbow 位置目标。

建议转换顺序：

```text
BVH FK 原坐标
  -> unit scale
  -> axis transform
  -> semantic skeleton
  -> keypoints pkl
```

## Debug 输出

BVH adapter 或入口至少应输出：

- `raw_height`
- `unit_scale`
- `up_axis`
- `lateral_axis`
- `forward_axis`
- `root_xyz_range`
- `head_minus_feet_mean`
- `left_right_hip_delta_mean`
- `foot_to_toe_delta_mean` 或 `foot_to_end_site_delta_mean`

## 常见错误判定

- 人整体躺倒：up 轴错，通常 `head.z` 不明显高于 foot，或人体高度落在 X/Y range。
- 人侧身站立或整体旋转 90 度：forward/lateral 轴错，通常 foot-to-toe 偏移不在 X 轴。
- 左右镜像：lateral 轴符号错，通常 left/right hip 或 shoulder 的左右关系反了。
- retarget 后全身 IK 误差都大：优先查单位和坐标系；如果只有局部肢体异常，再查 mapping 或 BVH rotation order。
- robot 在空中：优先查 keypoints pkl 中 `left_calf/right_calf` 或足端目标的最低 Z。如果最低 Z 仍在 1m 左右，说明 adapter 没有做 ground alignment，而不是 IK 本身的问题。
- 身高异常到 300cm 级：优先检查 BVH parser 是否把非 root joint 的 `OFFSET` 和 position channel 双加。
- 小腿方向大体跟随但脚尖朝向错误：检查 ankle/calf keypoint quaternion 是否误用 knee->ankle 向量构造。若 BVH 有 foot/toe/End Site，脚掌前向应参与 ankle/foot orientation。
- 大腿以下 link 相对大腿扭转、hip_yaw 大面积接近限位、但左右脚位置没有镜像或交叉：检查 thigh/knee keypoint quaternion 是否只用单根大腿向量构造。正确构造必须用 pelvis facing 固定 twist。
- 双臂肘部往身体中线凹陷：先查左右手臂目标相对 `shoulder_mean` 的 MuJoCo Y 符号。左臂应主要在 +Y，右臂应主要在 -Y；如果左右差异落在 X 或 Z，通常是 lateral/forward 轴映射错。若符号正确但肩中心偏移，再查 `LeftShoulder/RightShoulder` 是否接入 mapping，`shoulder_mean` 是否优先使用真实肩点。
- 手臂位置目标正确但 robot 手臂仍内凹：对比关闭手臂 orientation cost 前后的 elbow/wrist 位置误差。若误差显著下降，说明 BVH 手臂 orientation/roll 与机器人自由度冲突，应保留位置目标、降低手臂 orientation cost。
