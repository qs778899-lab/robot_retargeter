# Status

current_phase: followup_pns_leg
task_status: IN_PROGRESS

| Phase | Status | Notes |
|---|---|---|
| phase_1 | PASSED | 文档与接口定稿；范围已收敛为只适配 BVH，不适配 FBX |
| phase_2 | PASSED | 基础 BVH parser、mapping、单位/朝向 debug 与坐标变换测试通过 |
| phase_3 | PASSED | PNS/v3 discovery、metadata 解析、semantic skeleton、PNS End Site toe 和 Head fallback 测试通过 |
| phase_4 | PASSED | human_replay.py --help、单 BVH no-viewer smoke、pkl schema 和 Phase 2/3 回归测试通过 |
| phase_5 | PASSED | PNS/v3 keypoints pkl 生成、g1 robot_retarget smoke、CSV 行数检查和全量回归测试通过 |
| followup_v3_visual | PASSED | v3 完整动作可视化已由用户确认正常；修复包括 FK position channel、自动轴、ground alignment 和手臂 orientation override |
| followup_pns_leg | PENDING_USER | 已撤回 root orientation override；PNS 改为用 `LeftFoot/RightFoot` 脚掌朝向驱动 ankle/calf quaternion，并增加 PNS foot frame -> G1 ankle frame local Y `+90deg` 固定校准；v3 保持原链路，等待用户可视化复查 |
