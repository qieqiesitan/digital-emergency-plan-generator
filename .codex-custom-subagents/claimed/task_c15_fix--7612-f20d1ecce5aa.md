# Codex Custom Subagents task handoff v1

Task: task_c15_fix

## 任务：修复 C1-5 质量审查问题（采纳回滚/类型归一/POI 类型/批量一致性）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 fdc93b8。启动时 `cd` 到该目录，git status 确认干净。

### 关键 1：采纳失败回滚（StepRiskChemical / StepResources）

两个文件：采纳时**先 await 保存成功，再移动候选到已采纳区**；失败保留候选并提示：

```tsx
const accept = async (item: CandidateItem) => {
  try {
    const payload = toCreatePayload(item);
    await createChemical(enterpriseId, payload);   // 或 batchCreateResources
    setCandidates(prev => prev.filter(x => x._key !== item._key));
    setAccepted(prev => [...prev, item]);
    queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
  } catch (e: unknown) {
    message.error(extractError(e) || "保存失败，请重试");
  }
};
```

（保存成功才移动，失败候选保留在原处，杜绝 UI/后端不一致。）

### 重要 2：危化品 toCreatePayload 类型归一

`StepRiskChemical.tsx` 的 `toCreatePayload`：与 StepResources 一致做显式类型转换 + name 必填校验：

```tsx
const toCreatePayload = (item: CandidateItem): HazardousChemicalCreate => {
  const name = String(item.name || "").trim();
  if (!name) throw new Error("候选缺少化学品名称");
  return {
    name,
    cas_no: item.cas_no ? String(item.cas_no) : undefined,
    // ... 其余字段按 HazardousChemicalCreate 类型显式 String()/undefined
  };
};
```

（先读 types/hazardousChemical.ts 的 HazardousChemicalCreate 字段，全部显式转换；dict/list 等结构值转 String 或过滤。）

### 重要 3：AMAP POI 类型从后端响应消费

`StepSurrounding.tsx`：高德搜索的 POI 类型选项优先用 `searchAmapSurrounding` 响应中的 `available_types`（若存在），否则回退本地常量。先读 `types/enterprise.ts` 的 AmapSearchResult / AmapPoiTypeItem 确认结构。

### 重要 4：危化品批量写入一致性

先读 `frontend/src/services/hazardousChemicalService.ts` 确认是否有 `batchCreateChemicals`（后端有 `/chemicals/batch`）。若有：采纳时用 `batchCreateChemicals(enterpriseId, [payload])`；若没有：保持 `createChemical` 并在注释说明（后端有 batch 端点，可后续接入）。

### 步骤 5：验证 + Commit

运行：`cd frontend && npx tsc -p tsconfig.app.json --noEmit`

再运行：`cd frontend && npx eslint src/pages/Onboarding/`

预期：无类型/ESLint 错误。

```bash
git add frontend/src/pages/Onboarding/ frontend/src/services/hazardousChemicalService.ts
git commit -m "fix(onboarding): rollback on adopt failure, normalize payloads, consume amap types"
```

（若 hazardousChemicalService 未改动则只 add Onboarding 目录。）

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 先读相关文件确认类型/服务签名
2. 按步骤修复
3. tsc + eslint 验证
4. 提交
5. 自审：保存成功才移动候选（失败保留）？危化品 payload 类型归一 + name 校验？POI 类型消费 available_types？批量一致？
6. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、tsc/eslint 结果、提交 SHA、自审发现
