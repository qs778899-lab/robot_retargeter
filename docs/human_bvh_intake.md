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
- 身高约 `100 ~ 250`：大概率是厘米，`unit_scale=0.01`。
- 身高约 `1000 ~ 2500`：大概率是毫米，`unit_scale=0.001`。

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

