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
