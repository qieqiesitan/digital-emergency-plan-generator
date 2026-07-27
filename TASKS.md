## 当前状态快照（压缩恢复用）
- 正在做什么：预案列表筛选查询功能 — Docker 容器级验证通过
- 已完成：
  任务1 — planService.ts enterprise_id 改为可选
  任务2 — PlanListPage.tsx 重写为跨企业模式 + Table 服务端搜索/分页
  任务3 — PlanCardsPage.tsx 增加企业名搜索 + 行业筛选 + 全部预案列表入口
  任务4 — routes/index.tsx 注册 /plans/all 路由
  任务5 — 后端 + 前端 EnterprisePlanSummary.industry 字段（含 bug 修复：SELECT 列表 + GROUP BY）
  任务6 — 移动端 EnterprisePlanListScreen 搜索 + 状态筛选
  任务7 — 移动端 PlanCardsScreen 企业名搜索
- 验证结果（Docker 容器内）：
  - GET /api/v1/plans (cross-enterprise): 200 total=31
  - GET /api/v1/plans?search=PLC: 200 total=2
  - GET /api/v1/plans?plan_type=comprehensive: 200 total=11
  - GET /api/v1/plans?status=completed: 200 total=20
  - GET /api/v1/plans/enterprise-summary: 200 29 enterprises, industry 字段正常
  - frontend: npx tsc --noEmit 零错误
  - frontend: vite build 8514 modules transformed
- 修改文件清单（10 个）：
  - frontend: planService.ts, PlanListPage.tsx, PlanCardsPage.tsx, routes/index.tsx, types/plan.ts, EnterprisePlanListScreen.tsx, PlanCardsScreen.tsx
  - backend: schemas/plan.py, routers/plans.py
- Git savepoint: 2be61eb (实施前备份)
- Docker: 容器 emergency-plan-backend + emergency-plan-frontend 均已重启
