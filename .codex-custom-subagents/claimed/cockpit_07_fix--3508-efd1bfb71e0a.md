# Codex Custom Subagents task handoff v1

Task: cockpit_07_fix

你正在修复「企业驾驶舱」任务 7 质量审查发现的 1 项重要缺陷 + 3 项低成本次要项。只改下列内容，提交单独 commit。

## 工作目录（重要）
C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit
（git worktree，分支 codex/enterprise-cockpit。前端命令用 workdir 进入 frontend 子目录。）

## 缺陷 1（重要）：EnterpriseModulePage 查询失败永久 Spin + 无关模块也发企业查询

文件：`frontend/src/pages/Enterprise/EnterpriseModulePage.tsx`

根因：`isLoading || !enterprise` 分支在查询失败（isError、data=undefined）时落入永久 Spin；且查询对所有 6 个模块无条件启用，而 chemicals/resources/assessment/investigation 不消费 enterprise 数据。

修复：

1. `Ctx` 的 enterprise 改为可选，并调整两个依赖 enterprise 的 render 兜底：

```tsx
type Ctx = { enterpriseId: string; enterprise?: Enterprise };
```

`info.render` 改为：

```tsx
render: ({ enterprise }) =>
  enterprise ? (
    <>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
        <EditButton />
      </div>
      <EnterpriseInfoCards enterprise={enterprise} readOnly />
    </>
  ) : (
    <div>企业信息加载失败</div>
  ),
```

`surrounding.render` 改为：

```tsx
render: ({ enterpriseId, enterprise }) => (
  <SurroundingInfoPanel
    enterpriseId={enterpriseId}
    surroundingInfo={enterprise?.surrounding_info || { nearby_units: [], sensitive_targets: [], traffic_info: "" }}
    onRefresh={() => undefined}
  />
),
```

2. 页面主体改为按需查询 + 错误分支：

```tsx
export default function EnterpriseModulePage() {
  const { id, moduleKey = "" } = useParams<{ id: string; moduleKey: string }>();
  const navigate = useNavigate();
  const mod = MODULE_MAP[moduleKey];
  const needsEnterprise = moduleKey === "info" || moduleKey === "surrounding";
  const enterpriseQ = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id && needsEnterprise,
  });

  if (!mod) {
    return (
      <div>
        模块不存在
        <Button type="link" onClick={() => navigate(`/enterprises/${id}`)}>返回企业驾驶舱</Button>
      </div>
    );
  }
  if (needsEnterprise && enterpriseQ.isLoading) return <Spin size="large" />;
  if (needsEnterprise && (enterpriseQ.isError || !enterpriseQ.data)) {
    return (
      <div>
        企业信息加载失败
        <Button type="link" onClick={() => enterpriseQ.refetch()}>重试</Button>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={mod.title}
        subtitle={mod.en}
        onBack={() => navigate(`/enterprises/${id}`)}
      />
      {mod.render({ enterpriseId: id!, enterprise: enterpriseQ.data })}
    </div>
  );
}
```

3. 合并 `useParams`/`useNavigate` 为一行 import（`import { useNavigate, useParams } from "react-router-dom";`）。

## 缺陷 2（次要）：ModuleSideNav 楼层项双高亮 + 子串误匹配

文件：`frontend/src/components/enterprise/cockpit/ModuleSideNav.tsx`

`SideNavItem` 增加可选 `inactiveWhenSearch?: string`；活跃判定改为：

```tsx
const active = it.matchSearch
  ? location.pathname === it.to.split("?")[0] && location.search.includes(it.matchSearch)
  : location.pathname === it.to && !(it.inactiveWhenSearch && location.search.includes(it.inactiveWhenSearch));
```

`frontend/src/pages/Enterprise/enterpriseNavConfig.ts` 的「风险树编辑」项增加：

```ts
{ key: "tree", label: "风险树编辑", to: `/enterprises/${id}/risk-management`, inactiveWhenSearch: "floor=1" },
```

（效果：`?floor=1` 时仅「楼层平面图」高亮；无该参数时仅「风险树编辑」高亮。）

## 验证

运行（工作目录 worktree\frontend）：
- `npx tsc -b` → exit 0
- `npx eslint src/pages/Enterprise/EnterpriseModulePage.tsx src/components/enterprise/cockpit/ModuleSideNav.tsx src/pages/Enterprise/enterpriseNavConfig.ts` → exit 0
- `git diff --check` 干净

## Commit

```bash
git add frontend/src/pages/Enterprise/EnterpriseModulePage.tsx frontend/src/components/enterprise/cockpit/ModuleSideNav.tsx frontend/src/pages/Enterprise/enterpriseNavConfig.ts
git commit -m "fix(cockpit): module page error handling and side nav highlight"
```

## 项目规则
- TASKS.md 永不提交；不要修改任务范围外文件；你不是孤立的，不要 revert 他人修改。
- 按 AGENTS.md 铁律一，在 TASKS.md 顶部追加「当前状态快照」（不提交）。

## 汇报格式
- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修复内容、验证结果、commit SHA、自审发现
