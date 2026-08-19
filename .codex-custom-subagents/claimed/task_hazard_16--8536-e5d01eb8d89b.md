# Codex Custom Subagents task handoff v1

Task: task_hazard_16

## 目标

实现隐患管理任务 16「HazardDashboardPage + HazardTemplatePage + HazardPublicityPage + PublicHazardReportPage + PublicHazardPage」并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`1100018`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 契约

**文件**：新建 5 个页面（`frontend/src/pages/Hazard/` 下），修改 `frontend/src/routes/index.tsx`（占位替换为真实页面），按需扩展 `frontend/src/services/hazardService.ts`/`frontend/src/types/hazard.ts`/公开 service（报告取舍）。

**1. HazardDashboardPage（驾驶舱，规格 §12 + 任务 11 后端）**

- 指标卡：未闭环/未闭环风险点/整改及时率（None 显示「—」）/平均周期/重大挂牌（major_count+major_approved）/超期/月度环比/扫码待确认（消费 GET /dashboard metrics）。
- 图表：类型分布（饼图，hazard_type 分组）、月度趋势（近 12 月折线）、重大专表（Table）、企业对比（同账号多企业横向条形）。
- 未读角标：notifications 未读数（total/mine/by_type，展示 mine 或 total 取舍说明）。
- 导出按钮：台账/监管导出（axios blob，对齐既有 exportHazardLedger/Report）。
- 图表实现：无新重型依赖——可用 antd 自带或轻量方案（报告实现；若引入图表库需说明并跑门禁）。

**2. HazardTemplatePage（检查表模板，规格 §7 + 任务 4 后端）**

- 模板列表：GET /templates（系统+企业合并、企业优先，source/is_system 标识）。
- 企业模板 CRUD：新建/编辑（name/category/items 动态列表 content+expected_note）、复制系统模板（POST /templates/{id}/copy）、删除（Popconfirm）；系统模板行不显示编辑/删除（或 422 提示）。
- AI 生成：/ai/checklist-template（industry+risk_points → items 预填，失败降级不阻塞）。

**3. HazardPublicityPage（企业内公示，任务 10 后端）**

- 公示列表：GET /publicity（scope 过滤 ongoing/closed/all + 表格 code/title/level/status/rectification/source_type）。
- token 管理：展示当前 token（GET 需从公开链接或新增查询——报告取值方式）/生成/重置（POST /publicity-token）+ 复制公开链接按钮。
- 打印样式：提供打印友好样式或「打印」按钮（window.print，报告实现）。

**4. PublicHazardReportPage（扫码公开上报，/h/report/:token 免登录，规格 §8 + 任务 5 后端）**

- 免登录表单：description 必填 + location（企业通用 token 必填，风险点 token 可选）+ photo_urls + nonce（前端生成 uuid，隐藏字段）。
- 提交 POST /public/hazard/report/{token}；成功展示「已提交，待企业管理员确认」；409「请勿重复提交」提示（nonce 防重）；404「链接已失效」。
- 隐藏内部信息；不暴露企业/风险点内部数据（token 仅用于提交）。

**5. PublicHazardPage（公开公示页，/h/:token 脱敏，任务 10 后端）**

- 免登录：GET /public/hazard/{token}（企业名脱敏展示 + 列表 code/title/level/status/rectification/source_type + masked 标识 + generated_at）。
- 404「链接已失效」Result。

**6. 门禁**：`npx tsc -b` exit 0；eslint 改动文件 exit 0；`npx vitest run` 全绿（若扩展 service 补测试）；`git diff --check` 干净；后端全量 `python -m pytest tests/ -q` 无回归。

**7. 参考文件**（自行阅读）

- 后端：`backend/app/routers/hazard_management.py`（dashboard/templates/publicity/publicity-token）、`backend/app/routers/public_hazard.py`（report/publicity 契约）。
- 前端先例：`frontend/src/pages/Hazard/HazardInspectionTab.tsx`（导出 blob）、`frontend/src/pages/RiskPublicityPage.tsx` 或等价公开页（脱敏/公开页先例，查目录）、`frontend/src/services/hazardService.ts`。
- 规格：`docs/superpowers/specs/2026-08-14-hazard-management-design.md` §7、§8、§11.2、§12、§15。

## Commit

```bash
git add frontend/src/pages/Hazard/ frontend/src/routes/index.tsx frontend/src/services/ frontend/src/types/hazard.ts
git commit -m "feat(hazard): dashboard, templates, publicity and public pages"
```

按实际改动文件调整 add 列表；不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_hazard_16 --claim-id <claim_id> --exit-code 0 --summary "隐患驾驶舱模板公示公开页实现完成"
```

最终回复报告：task_id、claim_id、commit SHA、改动文件清单、门禁结果、设计决策说明（图表方案/未读口径/token 展示/打印样式/nonce 生成/脱敏）、git diff --check 结果。

## 规则

- 用 `apply_patch` 编辑；范围限制在任务文件所述文件；阻塞时停下汇报，不要跳过验证或伪造结果。
- 全程用简体中文交流；代码注释/变量名可用英文。
