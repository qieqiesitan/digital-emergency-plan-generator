# Codex Custom Subagents task handoff v1

Task: task_hazard_04

## 目标

实现隐患管理任务 4「检查表模板（系统默认 + 企业 CRUD + AI 生成）」并提交，为后续任务 12 AI 端点与前端模板页打基础。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`96e2c71`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 契约

**文件**：在既有 `backend/app/routers/hazard_management.py` 中追加模板端点、新建 `backend/app/services/hazard_ai_service.py`、新建 `backend/tests/test_hazard_template_api.py`。所有端点前缀沿用该 router 既有前缀 `/enterprises/{enterprise_id}/hazard-inspection`（与 §14 一致），AI 端点为 `/ai/checklist-template`。

**1. 模板端点**（规格 §5.9/§7）

- `GET /templates`：返回系统模板（enterprise_id NULL，is_system=True）与当前企业模板（enterprise_id=该企业）；企业模板可覆盖同名系统模板（列表返回时按（名称,分类）合并展示，企业条目优先——前端展示可说明来源）；归属校验沿用 router 既有 `_get_ent`/读权限惯例（非本企业 → 404）。
- `POST /templates`：企业自定义模板，body = name/category（daily/comprehensive/special/holiday）/items（`[{content, expected_note}]`，content 必填非空、expected_note 可空；items 空数组时 422）；企业内同名（同 category）模板冲突 409 或 422（说明取舍）；写权限=企业主/启用管理员（403）。
- `PUT /templates/{id}`：更新企业模板（name/category/items/enabled 语义按现有模型字段，模型无 enabled 则只 name/category/items）；系统模板不可直接编辑（422「系统模板请复制后编辑」）；非本企业模板 → 404。
- `POST /templates/{id}/copy`（或复用 POST body 中 copy_from 字段，选一种并说明）：系统模板复制为企业模板（深拷贝 items），供「系统模板复制后编辑」；复制后企业条目可编辑/删除。
- `DELETE /templates/{id}`：删除企业模板（系统模板不可删 422；非本企业 404）。
- 全部响应走 `ApiResponse` 信封；错误消息中文可读。

**2. AI 生成** `POST /ai/checklist-template`

- body：`{industry, risk_points}`（文本，industry 行业描述、risk_points 风险点/措施文本，可为空串但二选一必填，均空 422）。
- 服务函数（放 `hazard_ai_service.py`）：参考 `risk_dual_ai_service.py`/`risk_ai_service.py` 既有惯例——`llm_text_completion(timeout=60)`、`_parse_ai_json`、`ai_config_service.get_system_ai_config`；prompt 要求返回 items 数组 `[{content, expected_note}]`（8-15 项，中文，覆盖 人/机/料/法/环 检查要点）；任何异常/未配置/超时 → `available: false` + 空 items 降级（200），不阻塞流程（§16）。
- 端点：mock 可注入（测试通过 dependency override 或 monkeypatch 服务函数）；响应 `{available, items, note}`（items 含 content/expected_note）。
- 本任务不把 AI 结果自动落库（页面确认后由 POST /templates 落库）。

**3. 测试**（`backend/tests/test_hazard_template_api.py`，mock db 风格与 `tests/test_hazard_plan_api.py`/`test_enterprise_org.py` 一致）

- 项目测试约定：无 db fixture；服务/端点用 mock + `dependency_overrides`；async 测试必须 `@pytest.mark.asyncio`。
- 覆盖：GET 系统+企业合并列表；POST 创建（字段校验/items 校验/同名冲突/403）；PUT 更新企业模板 + 系统模板 422 + 非本企业 404；复制系统模板为企业；DELETE 企业模板/系统模板 422；AI 生成（成功 items 结构、输入为空 422、失败降级 available:false）。
- 断言必须有效无空断言；提交前跑目标测试 + 全量回归。

**4. 参考文件**（自行阅读）

- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §5.9、§7、§14、§16。
- 模型：`backend/app/models/hazard_management.py`（HazardChecklistTemplate）。
- 迁移：`backend/db_migration_hazard_management.sql` L5-20（含系统模板种子 5 张与 `uq_hazard_checklist_templates_system_name` 部分唯一索引）。
- 惯例参考：`backend/app/routers/hazard_management.py`（既有 _get_ent/_get_admin_ent/ApiResponse）、`backend/app/services/risk_dual_ai_service.py`、`backend/app/services/risk_ai_service.py`、`backend/tests/test_hazard_plan_api.py`。

## 验证

- `python -m pytest tests/test_hazard_template_api.py -v` 全部 PASS；
- `python -m pytest tests/ -q` 无回归（Event loop ResourceWarning 为既有非失败噪音）；
- `git diff --check` 干净。

## Commit

```bash
git add backend/app/routers/hazard_management.py backend/app/services/hazard_ai_service.py backend/tests/test_hazard_template_api.py
git commit -m "feat(hazard): checklist templates with AI generation"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_04 --claim-id <claim_id> --exit-code 0 --summary "隐患检查表模板+AI生成实现完成"
```

最终回复报告：task_id、claim_id、commit SHA、改动文件清单、目标测试与全量测试结果、设计决策说明（复制语义/同名冲突/系统模板保护/AI 降级）、git diff --check 结果。

## 规则

- 用 `apply_patch` 编辑；范围限制在任务文件所述文件；阻塞时停下汇报，不要跳过验证或伪造结果。
- 全程用简体中文交流；代码注释/变量名可用英文。
