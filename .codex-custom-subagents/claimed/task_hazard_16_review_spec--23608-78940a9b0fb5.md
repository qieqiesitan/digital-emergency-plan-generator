# Codex Custom Subagents task handoff v1

Task: task_hazard_16_review_spec

## 目标

对隐患任务 16「驾驶舱/模板/公示/公开页」提交 `c8dff5b`（父 `1100018`）做只读规格合规复审，输出复审报告。

## 工作目录

- **代码与 git 只读审查目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`c8dff5b`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。
- 规格文档：`docs/superpowers/specs/2026-08-14-hazard-management-design.md`（重点 §7、§8、§11.2、§12、§15）。

## 审查清单（逐项核验并给出证据）

1. **HazardDashboardPage**：指标卡（未闭环/风险点/及时率 None 显示「—」/平均周期/重大双口径/超期/环比/扫码待确认）消费 GET /dashboard；图表（类型分布饼图/月度趋势/重大专表/企业对比）字段与后端一致；未读角标（mine 主视角 + total/by_type 补充）；导出按钮 axios blob。
2. **HazardTemplatePage**：列表（系统+企业合并/企业优先/source/is_system 标识）；企业 CRUD + 复制 + 删除（系统模板无编辑/删除）；AI 生成（industry+risk_points → items 预填，失败降级）。
3. **HazardPublicityPage**：公示列表 scope 过滤 + 表格字段；token 展示（localStorage 缓存取舍说明）/生成/重置/复制链接；打印样式（@media print 隐藏操作区 + window.print）。
4. **PublicHazardReportPage**：免登录表单（description/location 按 token 类型必填/photo_urls/nonce）；nonce 前端生成（crypto.randomUUID 兜底）；409/404 独立提示；成功「已提交，待企业管理员确认」；不暴露内部信息。
5. **PublicHazardPage**：免登录消费后端脱敏数据（企业名掩码/masked/generated_at/公示行）；404「链接已失效」。
6. **门禁**：tsc -b/eslint/vitest 111/后端 952 全绿；git show --check 干净。
7. **无越界**：`git show c8dff5b --stat` 恰 9 个清单文件，消息精确匹配「feat(hazard): dashboard, templates, publicity and public pages」，TASKS.md 未提交（项目惯例）。

## 验证命令

- `npx tsc -b` exit 0、`npx vitest run` 全绿、`npx eslint` 改动文件 exit 0
- `python -m pytest tests/ -q`（预期 952 passed，Event loop ResourceWarning 为既有非失败噪音）
- `git show --check c8dff5b`（预期 exit 0）
- 只读审查：不修改任何源码文件；可按项目惯例更新 TASKS.md 台账。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_16_review_spec --claim-id <claim_id> --exit-code 0 --summary "隐患驾驶舱模板公示公开页规格复审通过"
```

最终回复报告：task_id、claim_id、commit SHA、逐项核验证据、测试结果、结论（✅ 通过 / ❌ 需修复，需修复时列问题清单含严重级）。

## 规则

- 全程只读；用 shell 读文件/跑测试；不修改源码。
- 阻塞时停下汇报。
