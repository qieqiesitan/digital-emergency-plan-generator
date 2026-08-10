# Codex Custom Subagents task handoff v1

Task: task_ai_generate_fix

## 任务：修复 AI 生成体验批次 2 项重要问题

你是实现子智能体。AI 生成体验修复的质量审查发现 2 项重要问题，请修复并提交。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2`（master 分支，HEAD 3b95404）。直接在主工作区修改提交。

### 审查发现（必须修复）

**重要 1：AI 生成接口超时对齐不完整**。`frontend/src/services/enterpriseService.ts:81`（generateSurroundingAI）、`emergencyResourceService.ts:88`（generateResourcesAI）、`hazardousChemicalService.ts:79`（generateChemicalsAI）、`riskSourceService.ts:88`（generateRiskSourcesAI）仍带每请求 `timeout: 120000` 覆盖，与后端 LLM 120s 超时**零余量**，前端计时更早开始 → 几乎总是前端先超时，errorDetail 只能透出英文 `timeout of 120000ms exceeded`，后端 504 中文 detail 到不了用户。

修法：把这 4 处每请求 timeout 改为 `180000`（与 api.ts 默认 180s 对齐，留 60s 余量），或直接删除覆盖走 api 默认。注意保持服务函数签名不变。

**重要 2：登出提示非过期场景误触发**。`frontend/src/services/api.ts` 401 刷新失败路径：无 refresh_token 时也抛错 → dispatch `auth:logout` → AuthContext 弹「登录已过期，请重新登录」。典型误触发：登录页密码错误（后端 401）时误弹。

修法：`api.ts` catch 分支中，**仅当存在 refreshToken 且刷新确实失败（refresh_token 无效/过期）时** dispatch `auth:logout`；无 refreshToken 的 401 直接 reject 不 dispatch（登录失败走页面自身错误提示）。确认 AuthContext handler 与登录页行为无回归。

### 质量门禁（必须全部通过）

1. `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
2. `npx eslint` 改动文件不得新增 error（与 HEAD 3b95404 逐项对比）
3. `git diff --check` 干净；不得新增 `any`；新增代码无 >100 字符行
4. 单提交、提交信息如 `fix(ai): align generate service timeouts and scope logout notice to expired sessions`，只含相关文件

### 提交

完成后 `git add` + `git commit`，运行 complete 脚本，报告：改动文件清单 + 提交 SHA、修法简述、门禁验证输出摘要。

