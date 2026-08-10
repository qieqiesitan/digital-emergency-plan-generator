# Codex Custom Subagents task handoff v1

Task: task_ai_generate_fix_review

## 任务：复审——task_ai_generate_fix（超时对齐 + 登出提示限定）

你是代码审查子智能体。AI 生成体验质量审查发现 2 项重要问题，实现者已修复（提交 eb43839）。请做合并复审（规格+质量合一，改动小）。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2`（master 分支，HEAD eb43839）。

审查命令：`git show eb43839`，逐文件阅读实际代码。

### 复审重点

1. **超时对齐**：4 个生成服务（enterpriseService/emergencyResourceService/hazardousChemicalService/riskSourceService）每请求 timeout 120000 → 180000，函数签名不变；无其他遗漏（如 exportService 120s 为导出不属于 AI 生成，确认不误改）。
2. **登出提示限定**：api.ts 401 刷新 catch 仅在存在 refreshToken 且刷新确实失败时清 token + dispatch auth:logout；无 refresh_token 的 401 直接 reject 不 dispatch；AuthContext handler 与登录页错误提示无回归。
3. 门禁：tsc/eslint/diff 全绿，无 any、无 >100 字符行。

### 汇报格式

```
结论：PASS / FAIL（✅ 通过 / ❌ 需修复）
逐项核验：...
参考建议（非阻塞）：...
```

