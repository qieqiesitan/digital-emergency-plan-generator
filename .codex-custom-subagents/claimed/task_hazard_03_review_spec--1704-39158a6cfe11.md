# Codex Custom Subagents task handoff v1

Task: task_hazard_03_review_spec

## 目标

对隐患任务 3「排查计划/任务/清单项端点」提交 `5af505b`（父 `16b3656`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`5af505b`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §5.1-5.3、§6、§14、§16）。
- 计划文档：`C:\Users\55061\Documents\数字化预案自动生成 2\docs\superpowers\plans\2026-08-15-hazard-management.md` 任务 3 契约（若工作树无计划文档，读主工作区该路径）。

## 审查清单（逐项核验并给出证据）

1. **计划 CRUD 契约**：字段按 §5.1（name/category/frequency/weekdays/zone_ids/template_id/responsible_user_id/ai_suggestion/enabled）；`zone_ids` 逐分区校验企业归属（422 列明不属于的分区）；`responsible_user_id` 校验为 enabled 的企业成员（422）；`template_id` 校验系统模板或本企业模板（422）；写=企业主/管理员（403）、读=归属（404）；端点 POST/GET/PUT/DELETE 齐全；DELETE 软删（enabled=False）且说明取舍（硬删级联破坏留痕/回填的合理性）。
2. **任务生成函数** `generate_tasks_for_plan`：按 frequency 生成任务（daily/weekly/custom 按 weekdays、monthly 约定说明）；`due_at` 默认当日 18:00；防重（同 plan 同日已存在则跳过）；items 组装 = zone_ids 内风险点+管控措施动态项 + 关联模板 items + AI 补全占位（不调 LLM，注释标明任务 12 入口）；title 格式、status=pending、责任人继承计划。
3. **任务/清单项端点契约**：`GET /tasks` 列表（责任人/状态/超期过滤、按 due_at 排序）；`GET /tasks/{id}` 详情含 items；`PUT /tasks/{id}` 提交核对（item 归属校验、result 枚举校验、非责任人 403/422、全部核对→done+completed_at、部分→processing）；`POST /tasks/{id}/to-record` 一键转隐患（仅 abnormal 项、source_type=inspection、source_task_id/source_item_id 回填、object_id/measure_id 取 item、code=HD-{三位序号} 生成不复用、photo_urls 继承）。
4. **路由挂载**：`main.py` 最小挂载（2 行），无越界改动；前缀与 §14 `/enterprises/{id}/hazard-inspection/plans|tasks` 一致；全部响应走 ApiResponse 信封。
5. **规格一致性**：与 B 规格 §6（任务执行/超期/转隐患）及 §16 错误语义（403/404/409/422）一致。
6. **测试有效性**：53 个测试断言有效无空断言；覆盖计划校验/生成组装/清单项提交/转隐患/权限边界。
7. **无越界**：`git show 5af505b --stat` 恰 4 个清单文件（main.py 3±/1、routers/hazard_management.py、services/hazard_service.py、tests/test_hazard_plan_api.py），消息精确匹配「feat(hazard): plan, task and checklist item endpoints」，`git show --check` 干净，TASKS.md 未提交（项目惯例）。

## 验证命令

- `python -m pytest tests/test_hazard_plan_api.py -v`（预期 53 passed）
- `python -m pytest tests/ -q`（预期 688 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check 5af505b`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_03_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患计划/任务/清单项端点规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
