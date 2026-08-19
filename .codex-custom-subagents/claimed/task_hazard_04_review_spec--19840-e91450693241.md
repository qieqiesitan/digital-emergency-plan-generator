# Codex Custom Subagents task handoff v1

Task: task_hazard_04_review_spec

## 目标

对隐患任务 4「检查表模板+AI 生成」提交 `b1bc6b2`（父 `96e2c71`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`b1bc6b2`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §5.9、§7、§14、§16）。
- 计划文档：`C:\Users\55061\Documents\数字化预案自动生成 2\docs\superpowers\plans\2026-08-15-hazard-management.md` 任务 4 契约。

## 审查清单（逐项核验并给出证据）

1. **模板端点契约**：`GET /templates` 系统+企业合并列表（企业条目优先、含 source/is_system）；`POST /templates` 创建（name/category/items 校验、items 空/非法 422、企业内同名同类别 409）；`PUT /templates/{id}` 更新企业模板、系统模板 422「复制后编辑」、非本企业 404；`POST /templates/{id}/copy` 复制（系统或本企业均可、deepcopy items、同名冲突 409）；`DELETE` 企业模板可删、系统模板 422、非本企业 404；写=企业主/启用管理员 403、读=归属 404。
2. **AI 端点契约**：`POST /ai/checklist-template` body=industry/risk_points（均空 422）；服务函数遵循既有 AI 惯例（llm_text_completion timeout=60、_parse_ai_json、get_system_ai_config）；prompt 要求 8-15 项中文 items（content/expected_note）；未配置/异常/超时/空 items → available:false + 空 items（200，§16 降级不阻塞）；端点不自动落库。
3. **规格一致性**：与 §5.9 字段（enterprise_id NULL=系统/is_system/items JSONB）、§7（系统默认库/企业自定义/复制系统模板后编辑/AI 检查表生成）、§14 接口前缀一致。
4. **测试有效性**：31 个测试断言有效无空断言；覆盖列表合并/创建校验/同名冲突/系统模板保护/复制/删除/AI 成功与降级。
5. **无越界**：`git show b1bc6b2 --stat` 恰 3 个清单文件（routers/hazard_management.py、services/hazard_ai_service.py、tests/test_hazard_template_api.py），消息精确匹配「feat(hazard): checklist templates with AI generation」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_template_api.py -v`（预期 31 passed）
- `python -m pytest tests/ -q`（预期 721 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check b1bc6b2`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_04_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患检查表模板规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
