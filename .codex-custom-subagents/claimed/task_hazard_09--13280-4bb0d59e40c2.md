# Codex Custom Subagents task handoff v1

Task: task_hazard_09

## 目标

实现隐患管理任务 9「联动回写派生 + 四色图叠加」并提交：未闭环隐患派生计数注入风险视图（层级树/总览/工作台/管控清单/告知卡），前端类型同步。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`3225ed2`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 契约

**文件**：`backend/app/services/hazard_service.py`（追加）、`backend/app/routers/risk_management.py`（workbench/overview/hierarchy 响应扩展）、`backend/app/schemas/risk_management.py`（schema 加字段）、`backend/app/services/risk_control_list_service.py`（管控清单扩展）、`backend/app/routers/risk_notice_card.py` 或对应服务（告知卡未闭环标记）、新建 `backend/tests/test_hazard_linkage.py`；前端类型文件（`frontend/src/services/riskManagementService.ts` 或 types 文件）同步字段。报告列出实际改动文件与取舍。

**1. 派生计数函数**（规格 §11.1）

- `hazard_service.py` 追加 `open_hazard_count(db, object_id=None, measure_id=None) -> int`：统计 `hazard_records` 中 status != "closed" 且（object_id 匹配 或 measure_id 匹配）的记录数；不修改风险源表字段（实时派生，闭环后归零）。
- 若同时传 object_id 与 measure_id，按 or 语义（说明）；两者都空返回 0。
- 可选辅助：`open_hazard_count_by_objects(db, object_ids)` 批量（workbench/overview 多分区场景，避免 N+1，报告实现）。

**2. 风险视图扩展**

- `WorkbenchZone`/`HierarchyZoneResponse`/管控清单条目 schema 增加 `open_hazard_count: int = 0` 字段；workbench/overview/hierarchy 端点组装时对每个分区/风险点填充该企业未闭环隐患数（按对象关联）。
- 风险层级树（hierarchy）：风险点层级追加 open_hazard_count。
- 管控清单（risk_control_list_service）：条目追加 open_hazard_count。
- 告知卡数据源：`risk_notice_card` 相关端点/数据服务追加「未闭环隐患」标记字段（如 `has_open_hazard: bool` 或 `open_hazard_count: int`，与既有告知卡结构一致，报告取舍）。
- 前端类型：`riskManagementService.ts`（或对应 types）为 WorkbenchZone/HierarchyZone/管控清单条目/告知卡类型补字段，保持与后端契约一致。

**3. 测试**（`backend/tests/test_hazard_linkage.py`，mock db 风格与既有一致，async 带 `@pytest.mark.asyncio`）

- 派生计数正确（object/measure 维度、未 closed 计数、closed 排除）；闭环后归零语义（mock 数据状态变化后重新计数）。
- 端点字段存在：workbench/overview/hierarchy/管控清单/告知卡响应含 open_hazard_count/has_open_hazard 字段且值正确。
- 断言有效无空断言；提交前跑目标测试 + 全量回归 + 前端 tsc/eslint（若改前端）。

**4. 参考文件**（自行阅读）

- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §11.1、§14（扩展 risk hierarchy/overview/notice card）。
- 模型：`backend/app/models/hazard_management.py`（HazardRecord.object_id/measure_id/status）。
- 既有端点：`backend/app/routers/risk_management.py`（workbench:370-460、overview:592-611、hierarchy:964-1006）、`backend/app/schemas/risk_management.py`（WorkbenchZone/HierarchyZoneResponse/OverviewResponse）、`backend/app/services/risk_control_list_service.py`、`backend/app/routers/risk_notice_card.py`。
- 惯例：`backend/tests/test_hazard_plan_api.py`（mock 风格）。

## 验证

- `python -m pytest tests/test_hazard_linkage.py -v` 全部 PASS；
- `python -m pytest tests/ -q` 无回归（Event loop ResourceWarning 为既有非失败噪音）；
- 若改前端：`npx tsc -b` exit 0、改动文件 eslint exit 0；
- `git diff --check` 干净。

## Commit

```bash
git add backend/app/services/hazard_service.py backend/app/routers/risk_management.py backend/app/schemas/risk_management.py backend/app/services/risk_control_list_service.py backend/app/routers/risk_notice_card.py backend/tests/test_hazard_linkage.py frontend/src/services/riskManagementService.ts
git commit -m "feat(hazard): derived open-hazard linkage on risk views"
```

按实际改动文件调整 add 列表（可含前端 types）；不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_09 --claim-id <claim_id> --exit-code 0 --summary "隐患派生联动回写实现完成"
```

最终回复报告：task_id、claim_id、commit SHA、改动文件清单、目标测试与全量测试结果、设计决策说明（批量计数/字段取舍/告知卡标记）、git diff --check 结果。

## 规则

- 用 `apply_patch` 编辑；范围限制在任务文件所述文件；阻塞时停下汇报，不要跳过验证或伪造结果。
- 全程用简体中文交流；代码注释/变量名可用英文。
