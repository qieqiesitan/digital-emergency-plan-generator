# PRD-08：工作台（仪表盘）

> **版本**：1.0 | **创建日期**：2026-06-05 | **依赖**：PRD-00, PRD-01, PRD-02, PRD-05

---

## 1. 模块概述

工作台是用户登录后的默认首页，提供全局数据概览和快捷操作入口。帮助用户快速了解工作状态并导航到核心功能。

**设计原则**：信息密集但条理清晰，操作路径最短。不使用大量留白和装饰性元素。

---

## 2. 功能点

| 编号 | 功能 | 描述 | 优先级 |
|------|------|------|--------|
| H01 | 概览统计卡片 | 4 张数字卡片展示核心指标 | P0 |
| H02 | 最近编辑列表 | 最近修改的 5 个预案快速入口 | P0 |
| H03 | 快捷新建入口 | 一键创建三类预案 | P0 |
| H04 | 全局搜索 | 跨企业和预案搜索 | P2 |

---

## 3. 数据接口

### 3.1 仪表盘聚合数据

```
GET /api/v1/dashboard
Authorization: Bearer <access_token>
```

**响应**：
```json
{
  "code": 0,
  "data": {
    "stats": {
      "enterprise_count": 3,
      "plan_count": 8,
      "completed_plan_count": 5,
      "risk_source_count": 24
    },
    "recent_plans": [
      {
        "id": "uuid",
        "title": "XX化工-综合应急预案",
        "plan_type": "comprehensive",
        "enterprise_name": "XX化工有限公司",
        "status": "draft",
        "completed_sections": 18,
        "total_sections": 28,
        "updated_at": "2026-06-05T10:30:00Z"
      }
    ],
    "recent_enterprises": [
      {
        "id": "uuid",
        "name": "XX化工有限公司",
        "plan_count": 3,
        "updated_at": "2026-06-03T08:00:00Z"
      }
    ]
  }
}
```

**后端实现**：
```python
async def get_dashboard(user_id: UUID, db: AsyncSession) -> dict:
    # 统计
    enterprise_count = await db.scalar(
        select(func.count(Enterprise.id)).where(
            Enterprise.user_id == user_id,
            Enterprise.deleted_at.is_(None)
        )
    )
    plan_count = await db.scalar(
        select(func.count(PlanProject.id)).where(
            PlanProject.user_id == user_id,
            PlanProject.deleted_at.is_(None)
        )
    )
    completed_count = await db.scalar(
        select(func.count(PlanProject.id)).where(
            PlanProject.user_id == user_id,
            PlanProject.status == ''completed'',
            PlanProject.deleted_at.is_(None)
        )
    )
    # 最近 5 个预案
    recent_plans = (await db.execute(
        select(PlanProject).where(
            PlanProject.user_id == user_id,
            PlanProject.deleted_at.is_(None)
        ).order_by(PlanProject.updated_at.desc()).limit(5)
    )).scalars().all()

    return {
        "stats": {
            "enterprise_count": enterprise_count,
            "plan_count": plan_count,
            "completed_plan_count": completed_count,
            "risk_source_count": await self._count_risk_sources(user_id, db),
        },
        "recent_plans": [...],
        "recent_enterprises": [...],
    }
```

---

## 4. 前端页面设计

### 4.1 整体布局

```
┌──────────────────────────────────────────────────┐
│  [Logo]  工作台                   [企业选择器 ▾] [用户头像] │
├──────────┬───────────────────────────────────────┤
│          │                                       │
│  侧边栏   │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ │
│  工作台   │  │ 企业  │ │ 预案  │ │已完成 │ │风险源 │ │
│  企业管理  │  │  3   │ │  8   │ │  5   │ │ 24   │ │
│  预案列表  │  └──────┘ └──────┘ └──────┘ └──────┘ │
│          │                                       │
│          │  快捷新建                              │
│          │  ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│          │  │综合预案  │ │专项预案  │ │现场处置  │  │
│          │  │  ↗      │ │  ↗      │ │方案 ↗   │  │
│          │  └─────────┘ └─────────┘ └─────────┘  │
│          │                                       │
│          │  最近编辑                              │
│          │  ┌─────────────────────────────────┐  │
│          │  │ XX化工-综合应急预案               │  │
│          │  │ 草稿 · 18/28 章节 · 2 小时前      │  │
│          │  ├─────────────────────────────────┤  │
│          │  │ XX制造-火灾专项预案                │  │
│          │  │ 已完成 · 全部章节 · 昨天           │  │
│          │  └─────────────────────────────────┘  │
└──────────┴───────────────────────────────────────┘
```

### 4.2 统计卡片

四张卡片水平排列，每张含：
- 图标（Ant Design Icon）
- 数字（大字号、加粗）
- 标签文本

```
企业数    预案总数    已完成    风险源数
  🏭       📋        ✅        ⚠️
  3        8         5         24
```

点击卡片 → 跳转对应列表页（企业列表/预案列表/预案列表已完成筛选/风险源管理）

### 4.3 快捷新建

三个按钮卡片，每个含：
- 预案类型图标
- 预案类型名称
- 简短描述（如"企业整体应急框架"）

点击 → 进入新建预案向导，自动选中对应类型

### 4.4 最近编辑列表

- 5 条最近编辑的预案记录
- 每条含：预案标题、类型 Tag、企业名称、状态 Tag、章节进度条、相对时间
- 点击条目 → 进入预案编辑器
- 底部「查看全部 →」→ 跳转预案列表

---

## 5. 全局企业切换器

位于顶部导航栏，下拉选择当前工作的企业：

```
[ XX化工有限公司 ▾ ]
├─ XX化工有限公司
├─ XX制造有限公司
└─ XX贸易有限公司
```

**行为**：
- 切换后，全局状态中的 `currentEnterpriseId` 更新
- 预案列表、编辑器上下文自动切换到所选企业
- 如果当前正在编辑预案且不属于新企业，先保存并提示

**实现**：
```typescript
// contexts/EnterpriseContext.tsx
const EnterpriseContext = createContext<{
  currentEnterpriseId: string | null;
  enterprises: Enterprise[];
  setCurrentEnterprise: (id: string) => void;
}>(...);
```

---

## 6. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC72 | 统计数字正确 | 自动化：GET /dashboard → stats 与实际数据一致 |
| AC73 | 统计卡片渲染 4 个指标 | E2E：页面加载 → 4 个卡片可见 |
| AC74 | 最近编辑列表显示 5 条 | 自动化：创建 6 个预案 → dashboard 显示最近 5 条 |
| AC75 | 点击最近预案跳转编辑器 | E2E：点击 → URL 变为 /plans/:id/edit |
| AC76 | 快捷新建综合预案 | E2E：点击"综合预案"→ 进入新建向导 |
| AC77 | 企业切换器生效 | E2E：切换企业 → 预案列表刷新 |
