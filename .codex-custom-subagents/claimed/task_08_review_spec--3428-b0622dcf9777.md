# Codex Custom Subagents task handoff v1

Task: task_08_review_spec

## 目标

对「风险分级管控增强（A 阶段）」任务 8 的实现做**只读规格合规审查**，对照 A 规格 §7/§8/§9/§11 与任务 8 交接单，输出结论与问题清单。**只审查，不改任何代码。**

## 审查对象

- 工作树：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`）
- 提交：`70c9b57`（父 `fe73ba6`）
- 文件：
  - `backend/app/services/risk_control_list_service.py`
  - `backend/app/routers/risk_management.py`
  - `backend/app/routers/public_risk.py`
  - `backend/app/main.py`
  - `backend/tests/test_risk_control_list.py`
- 规格：`docs/superpowers/specs/2026-08-14-risk-control-enhancement-design.md` §7（管控清单：行字段/默认映射/筛选/导出）、§8（公示：口径/脱敏/token）、§9（接口）、§11（错误处理：token 无效 404、公开脱敏）

## 审查要点

1. 清单服务：行字段与 §7 一致（含 zone_id/object_id 内部键用于筛选）、默认映射键值正确（value.level→control_level）、`build_ledger_workbook` 表头与行键映射正确；
2. control-list 端点：floor 缺省默认楼层、筛选（zone_id/level 匹配 current 或 inherent/control_level/keyword）、分页、响应去内部键；
3. export：xlsx Content-Disposition/媒体类型正确；
4. 公示：token 缺省生成/重置、口径（current==重大 or control_level==企业）、公开端点脱敏（无 person/phone）、无效 token 404「链接已失效」、多楼层企业口径（实现者决策评估）；
5. main.py 注册 public_risk；
6. 测试：16 用例覆盖服务/端点/公开 404/脱敏；
7. 无越界改动：提交仅含上述 5 个文件。

## 输出格式

- 结论：✅ 符合规格 / ❌ 需修复
- 问题清单：**必须修复 / 建议修改 / 仅供参考**，含文件与行号
- 说明：只读审查，未修改任何文件

## 完成协议

认领后记下 `claim_id`。最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_08_review_spec --claim-id <claim_id> --exit-code 0 --summary "任务8规格审查完成"
```

## 规则

- 全程只读（可运行只读 pytest、git log/show/diff）；
- 任务池命令在任务池目录执行；代码审查在工作树目录进行。
