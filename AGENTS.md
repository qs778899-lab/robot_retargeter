---
name: humanoid
description: |
  人形机器人项目功能实现的工程规范 。当用户在进行人形机器人相关功能二次开发、代码集成、问题排查时有用。
---
# AGENTS.md

Always answer in Chinese.

本文件定义本项目的工程规范。

在进行任何代码修改、重构、调试、问题分析、功能开发之前，必须先阅读并遵守本文档中的全部规则。

# Humanoid Robot 工程规范

## 代码实现原则

- 将参考代码链路进行细致拆分，理清每一个环节的输入输出
- 尽量小改动，尽量不修改原代码库的代码文件
- 尽量复用原代码库已有的函数或类
- 复杂项目实现/功能修改时，逐步实现过程中需要逐步分块自查
- 对风险较高的实验性改动（例如新算法版本、优化器、动力学/IK策略调整），必须优先在独立实验分支或独立 worktree 中开发，避免影响日常开发分支。
- 实验分支合并前，至少完成低资源 smoke/performance 测试并记录关键指标；只有结果与基线同量级或差异有明确解释时，才允许考虑合并到日常分支。

## 二次开发项目/代码文件结构规范

  本文用于指导 AI Agent 或开发者在项目二次开发中保持代码结构清晰、职责边界明确、便于多人协作和后续迁移。本文不绑定具体业务，可以用于数据处理、模型推理、批处理、云平台任务、格式适配、后处理等不同类型项目。

### 核心目标

  - 让核心逻辑、输入适配、批处理编排、平台逻辑、后处理逻辑解耦。
  - 让新增功能时尽量新增模块，而不是反复修改核心文件。
  - 让不同开发者可以并行开发，减少 merge 冲突。
  - 让 AI Agent 能快速判断“这个需求应该改哪里，不应该改哪里”。
  - 让代码结构可以迁移到其他项目，而不是绑定某个具体任务。

### 高层结构原则

  - 顶层入口只做编排，不写格式私有逻辑。
    顶层入口可以负责 CLI 参数、任务发现、输出目录、并行、断点续跑、结果转换、检查、报告和 summary；不应直接包含某种输入格式的解析、命名规则、目录规则或转换细节。

  - 不要用一个批处理入口直接调用另一个批处理入口。
    批处理入口之间互相调用会形成多层控制逻辑，导致参数传递、输出结构、失败统计、并行策略、断点续跑和后处理难以统一。更好的方式是多个入口共享底层 adapter、workflow、core engine。

  - 新输入格式优先新增适配层和接入层，而不是修改顶层入口或核心流程。
    新格式的数据读取、字段解析、文件命名、目录发现、标准化转换应放在独立模块中；顶层入口只通过稳定接口调用这些模块。

  - adapter 和 runner / orchestrator 必须分工清楚。
    adapter 回答“这种原始数据怎么读、怎么标准化”；runner / 接入层回答“这种数据怎么接入统一批处理流程”；orchestrator / 顶层入口回答“任务如何统一执行、保存、检查和汇总”。

  - 核心算法只处理标准中间表示，不关心原始数据来源。
    原始数据格式、目录结构、文件命名、平台路径等差异应在进入核心算法前被消化掉。核心算法的输入输出应尽量稳定。

  - workflow 只表达通用处理步骤，不放平台或数据集专属规则。
    workflow 可以串联标准步骤，例如预处理、校验、转换、核心处理、结果导出；但不应硬编码某个平台、某个数据集或某种文件命名习惯。

  - 后处理只消费标准输出，不反向污染核心流程。
    检查、报告、标注、过滤、上传、可视化等后处理逻辑应基于核心流程已经生成的标准结果，避免把后处理需求反向写进核心算法。

  - 保留旧入口作为兼容层，不轻易删除。
    当项目迁移到统一入口或新架构后，旧入口可以逐步收敛为 thin wrapper，但不应在新入口稳定前删除，以保证本地调试、旧命令和已有工作流可继续使用。

  - 从实验分支或参考实现迁移功能时，以稳定主线为基底增量合并。
    不要用实验版本直接覆盖稳定主线文件。应先识别稳定主线已有的生产能力，再选择性迁移参考实现中的可复用模块。

  - 结构重构必须证明行为不变。
    如果目标是重构而不是改变算法，必须对旧链路做回归验证。关键输出应与修改前一致；允许差异必须有明确解释，例如时间戳、临时路径、日志顺序等非确定性字段。

  - 文档必须区分“已实现能力”和“计划中能力”。
    README、任务计划和注释不能把未来计划写成当前事实。未完成的格式、入口、参数或工作流必须明确标注为后续阶段。

### 通用分层原则

  推荐把项目拆成以下几层：

  原始输入
    ↓
  adapter / loader / parser
    ↓
  标准中间表示
    ↓
  core engine
    ↓
  workflow
    ↓
  entrypoint
    ↓
  postprocess / report / export

  各层含义：

  - adapter / loader / parser：处理不同输入格式、文件命名、目录结构、字段映射。
  - 标准中间表示：项目内部统一的数据结构或文件格式。
  - core engine：真正的核心算法或核心业务逻辑。
  - workflow：把多个核心步骤串起来的通用流程。
  - entrypoint：命令行入口、云平台入口、本地调试入口。
  - postprocess / report / export：结果转换、检查、报告、标注、上传等后处理。

  核心要求：

  - 核心算法不关心原始数据格式。
  - workflow 不关心云平台目录结构。
  - entrypoint 不重复实现核心流程。
  - adapter 不修改核心算法。
  - postprocess 不反向污染核心流程。

### 推荐文件结构

  通用项目可以参考：

  project_root/
    README.md
    agentd.md

    #放“可复用的项目代码”，也就是核心 Python package。
    src/ 或 project_package/
      core/
        engine.py
        config.py
        versions.py

      workflow/
        batch_workflow.py
        common.py

      adapters/
        base.py
        format_a.py
        format_b.py

      postprocess/
        checker.py
        exporter.py
        reporter.py

      utils/
        io.py
        logging.py
        validation.py

    tools/
      run_local.py
      run_cloud.py
      inspect_input.py
      convert_format.py
      
    #放“可直接执行的小脚本”或薄 wrapper。
    scripts/
      thin_wrapper.py

    configs/
      default.yaml
      mappings/
        format_a.json
        format_b.json

    tests/
      fixtures/
      test_workflow.py

### 新功能开发原则

  新增功能时，先判断它属于哪一层：

  新输入格式     → adapters/
  新算法版本     → core/versions.py + core/engine.py
  新批处理流程   → workflow/
  新运行入口     → tools/run_xxx.py
  新平台支持     → tools/run_cloud.py 或 platform adapter
  新检查/报告    → postprocess/
  新配置         → configs/

  不要一上来就修改最大、最核心的文件。

### Version 管理原则

  如果项目存在版本迭代，例如算法版本、配置版本、处理策略版本，应集中管理。

  推荐：

  core/versions.py

  职责：

  - 注册支持的版本。
  - 定义默认版本。
  - 定义版本兼容关系。
  - 定义版本推断规则。
  - 校验非法组合。

  不要让多个入口文件各自维护一份版本逻辑。

### 测试要求

  结构调整后至少验证：

  - 入口 --help 能正常显示。
  - 核心模块能编译。
  - 旧输入样例能跑通。
  - 新输入样例能跑通。
  - 输出目录结构符合文档。
  - 关键输出与修改前一致，或差异有明确解释。
  - 不产生多余缓存、临时文件、重复 JSON。
  - 不破坏已有入口。

   推荐测试类型：
  unit test       # core / adapters
  smoke test      # entrypoint
  golden test     # 输出对比
  regression test # 修改前后结果对比


## Execution Loop (Mandatory)

For ANY task in `tasks/*`:

Repeat until completion:

1. Read tasks/<active_task>/status.md
2. Identify current_phase
3. Execute ONLY that phase
4. Run ALL tests in test_matrix.md for that phase
5. If tests pass:
   - mark phase PASSED in status.md
   - move to next phase
6. If tests fail:
   - fix code
   - rerun SAME tests
   - do NOT proceed
7. Only when ALL phases are PASSED:
   - mark task COMPLETE

If you stop early, it is considered FAILURE.

### 项目任务和测试工作流的结构推荐
  repo/
  │
  ├── AGENTS.md                  # 全局行为规范（所有任务共用）
  ├── README.md                  # 项目说明
  ├── docs/
  │   ├── project_spec.md       # 项目级规范（结构 / 架构 / test）
  │   ├── architecture.md
  │
  ├── tasks/                    # ⭐核心：任务空间
  │   ├── refactor_v1/          # 一个任务 = 一个目录
  │   │   ├── plan.md           # 总计划（phase定义）
  │   │   ├── status.md         # 当前执行状态（机器可读）
  │   │   ├── test_matrix.md    # 验收标准（强约束）
  │   │   ├── log.md            # 执行日志（可追加）
  │   │   └── artifacts/        # 生成的中间产物（patch / diff / notes）
  │   │
  │   ├── exp_feature_x/
  │   │   ├── plan.md
  │   │   ├── status.md
  │   │   ├── test_matrix.md
  │   │   └── log.md
  │
  ├── src/
  └── tests/

## 常见工程细节易错

### 关节顺序问题（BFS vs DFS）     

**MuJoCo / URDF**：对运动学树做**深度优先（DFS）**遍历定义 DOF 顺序。
结果是"身体部位"分组：一条支链走到底再换下一条。

```
MuJoCo G1 DOF 顺序（DFS）:
 0-5:  left_hip_pitch/roll/yaw, left_knee, left_ankle_pitch/roll
 6-11: right_hip_pitch/roll/yaw, right_knee, right_ankle_pitch/roll
12-14: waist_yaw/roll/pitch
15-21: left_shoulder_pitch/roll/yaw, left_elbow, left_wrist_roll/pitch/yaw
22-28: right_shoulder_pitch/roll/yaw, right_elbow, right_wrist_roll/pitch/yaw
```

**IsaacLab MotionLib**：对运动学树做**广度优先（BFS）**遍历定义 DOF 顺序。
结果是"关节类型"分组：同一深度层的关节排在一起（左右腿/腰同类关节相邻）。

```
IsaacLab G1 DOF 顺序（BFS）:
 0-2:  left_hip_pitch, right_hip_pitch, waist_yaw        (depth 1)
 3-5:  left_hip_roll,  right_hip_roll,  waist_roll        (depth 2)
 6-8:  left_hip_yaw,   right_hip_yaw,   waist_pitch       (depth 3)
 9-10: left_knee,      right_knee                         (depth 4)
11-12: left_shoulder_pitch, right_shoulder_pitch           (depth 4)
13-14: left_ankle_pitch,    right_ankle_pitch              (depth 5)
15-16: left_shoulder_roll,  right_shoulder_roll            (depth 5)
17-18: left_ankle_roll,     right_ankle_roll               (depth 6)
19-20: left_shoulder_yaw,   right_shoulder_yaw             (depth 5)
21-22: left_elbow,          right_elbow                    (depth 6)
...
```

`G1_ISAACLAB_TO_MUJOCO_DOF`（定义于 `tools/sonic_eval/motionlib_provider.py`）是两种顺序之间的转换索引，
`dof_pos_mujoco = dof_pos_isaaclab[G1_ISAACLAB_TO_MUJOCO_DOF]`。

#### 典型踩坑：张量顺序写错

将 IsaacLab BFS 顺序的张量写成了 MuJoCo DFS（身体部位）顺序：

```python
# 错误写法（身体部位顺序）：
G1_DEFAULT_ANGLES_ISAACLAB = [-0.312, 0.0, 0.0, 0.669, ...]
# 在此: index 3 = 0.669 原意是 left_knee
# 但 IsaacLab 语境下 index 3 = left_hip_roll → 渲染出 38° hip abduction = "双脚大跨"

# 正确写法（BFS 顺序）：
G1_DEFAULT_ANGLES_ISAACLAB = [-0.312, -0.312, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.669, ...]
# index 0,1 = left/right hip_pitch; index 9 = left_knee = 0.669
```

**诊断方法**：怀疑 IsaacLab 张量顺序有误时，将张量经 `G1_ISAACLAB_TO_MUJOCO_DOF` 重排后逐关节打印，检查关键关节值（hip_roll、knee）是否符合物理预期。

### 坐标系约定（up 轴 / forward 轴 / 手系）

人形项目跨工具协作时**坐标系约定不一致是最常见错误源**，比 DOF 顺序更隐蔽（DOF 错会立即看到姿态崩坏，坐标系错可能只是整体 90° 旋转，看起来"动作还算合理"但 retarget 数值全错）。

### BVH 单位与人体朝向专项规则

处理 human motion BVH、BVH adapter 或 BVH retarget 数据接入任务时，必须先阅读并遵守 `docs/human_bvh_intake.md`。至少要实证确认并记录 `raw_height`、`unit_scale`、`up_axis`、`lateral_axis`、`forward_axis`；不能只根据文件名、采集系统名或经验假设单位和朝向。

#### 常见工具的默认约定

| 来源 | UP | Forward | Lateral | 手系 |
|------|----|---------|---------|------|
| Maya / MotionBuilder / Mixamo BVH | +Y | +Z | +X (left) | 右手 |
| 部分 Blender / 旧版 3ds Max | +Z | +Y | +X | 右手 |
| MuJoCo / Isaac / URDF 默认 | +Z | +X | +Y (left) | 右手 |
| Unity | +Y | +Z | +X (right) | **左手** |
| Unreal | +Z | +X | +Y (right) | **左手** |

#### 实证判定方法（拿到陌生数据时）

不要靠"它应该是 Maya"或"它叫 BVH 所以一定 Y-up"，直接从数据本身读：

1. **UP 轴**：算 rest pose 下 Head 和 Foot 的位置差，**ΔX/ΔY/ΔZ 中最大那个就是 up**
2. **Lateral 轴**：算 LeftShoulder − RightShoulder，**最大差所在轴 = 左右轴**（同时正负号告诉你"+ 方向 = 左还是右"）
3. **Forward 轴**：T-pose 在 forward 方向对称（看不出来），改看 root 位移信息 ——
   - **前提**：先和 user 确认动作类型。仅当动作以**水平移动为主**（走/跑/跳跃位移）时，"root 位移范围最大的轴"才能等于 forward 轴
   - **不适用情况**：弯腰、下蹲、坐下、原地伸手等"非位移"动作 —— root 主要在 up 轴上下起伏（弯腰时髋下移）或仅在窄范围内抖动，此时位移最大的轴可能是 up 轴或随机噪声，无法用此法判定
   - 不适用时可改看：toe joint 相对 heel/ankle 的水平偏移方向（脚尖朝前）、End Site 在 hand/head 的偏移、或直接靠 facing 公式实测对比
4. **Forward 正方向**：看 root.Yrotation frame 0 值 / toe 相对 heel 的偏移 / 看动作语义；或直接试两种 facing 公式看哪个 retarget 误差小

#### 坐标系变换的工程实践

跨工具时一定要做一次显式的轴变换，**不要靠运气**：

- 项目内统一一个"内部坐标系"（通常跟目标机器人对齐，如 MuJoCo Z-up + X-forward）
- 所有外部输入（BVH/USD/FBX）在加载边界处做一次 R_facing 旋转
- 变换矩阵集中维护、不要散落在多个文件里
- **轴变换参数必须三处一致**：config 生成时、retarget 时、可视化时（错一处就全错）

#### 典型踩坑：忘了角色朝向

只换 up 轴（Y→Z）但不换 forward 轴，导致角色"躺下"或"侧身"站着。判断：retarget 后 G1 各关节位置误差全身性大（>10cm），数值越大越可能是 forward 轴错了；如果只是局部关节错，更可能是 DOF 顺序问题。

### 帧时间对齐

涉及参考动作（reference）与实际输出动作的对比分析时：

- 注意每一帧时间的严格对齐
- 如果无法严格对齐，需分析并给出原因

## 出现问题时

先给出具体方案，说明每一个环节具体怎么做。

若无法确定具体原因，可以通过增加日志输出的方式进行详细分析判断：
- 日志保存不能占用几十 GB 的空间
- 需要有及时清理的机制

## 问题排查的可行方案

- 可视化
- Test case
- 拆分参量的数值记录文件
