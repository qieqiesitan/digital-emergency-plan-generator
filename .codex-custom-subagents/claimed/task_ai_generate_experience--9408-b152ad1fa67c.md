# Codex Custom Subagents task handoff v1

Task: task_ai_generate_experience

## 任务：AI 生成体验修复（超时/错误提示/登录过期提示）

你是实现子智能体。用户反馈「风险与危化品页点击 AI 生成后一直加载、超时报错、控制台 401 与一堆警告」。已完成诊断，请按以下结论修复并提交。工作目录为主工作区。

### 诊断结论（已确认，不必重复排查）

- 401：用户 access token 过期，前端拦截器自动刷新后重试成功（后端日志 401→200），属正常自愈；控制台 401 是浏览器网络记录。
- 「一直加载+超时」：后端 LLM 调用 120s 超时（`backend/app/services/llm_client.py` 已有，超时抛 504「AI 响应超时，请稍后重试」），但前端 axios timeout=600000ms（10 分钟），且引导页生成 catch 用 `(e as Error).message`（axios 只给「Request failed with status code 504」，**后端 detail 未透出**），用户看到无意义的超时报错。
- antd 警告（valueStyle/List/destroyOnClose/Drawer width/rowKey/message 静态函数）：antd 6 deprecation 提示，非致命，**本次不清理**（范围大，记录为技术债即可），但不要新增同类警告。

### 修复项

1. **前端超时对齐**：`frontend/src/services/api.ts` 的 axios `timeout: 600000` 改为 `180000`（后端 120s + 余量）。
2. **引导页生成错误透出后端 detail**：`frontend/src/pages/Onboarding/` 各步骤生成/导入的 catch 统一改为解析 axios error：`e.response?.data?.detail || e.message || "生成失败"`（参考 StepOrg 现有写法 `axios.isAxiosError(e) && e.response?.data?.detail`）。涉及：StepRiskChemical、StepResources、StepSurrounding、StepOrg、ImportDrawer（如批次 A 已改动这些文件，基于新代码继续改）。
3. **生成中 loading 文案**：各步骤 AI 生成按钮 loading 文案统一提示「AI 生成中，通常需要 1-2 分钟，请耐心等待」（现有「生成中…」替换或补充，避免用户以为卡死）。
4. **登录过期友好提示**：`frontend/src/contexts/AuthContext.tsx` 的 `auth:logout` handler 增加一次性提示「登录已过期，请重新登录」（用 antd message 或轻量 toast；若用静态 message 会带 deprecation 警告，可接受并注明）。
5. **后端**：确认 llm_client.py 120s 超时与 504 提示已存在（只读确认，不改）。

### 质量门禁（必须全部通过）

1. `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
2. `npx eslint` 改动文件不得新增 error（与 HEAD 逐项对比）
3. `git diff --check` 干净；改动文件不得新增 `any`；新增代码无 >100 字符行
4. 单提交或按项拆提交，信息清晰，只含相关文件

### 提交

完成后 `git add` + `git commit`，运行 complete 脚本，报告：改动文件清单 + 提交 SHA、修法简述、门禁验证输出摘要。

