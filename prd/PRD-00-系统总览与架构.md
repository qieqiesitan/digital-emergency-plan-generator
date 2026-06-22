# PRD-00：系统总览与架构

> **版本**：1.0 | **创建日期**：2026-06-05 | **关联文档**：技术方案 v1.0、功能清单 v1.0

---

## 1. 产品概述

### 1.1 产品定义

「数字化应急预案自动生成系统」是一款面向企业安全管理人员的 Web 应用。用户通过结构化表单录入企业安全数据，系统基于 **GB/T 29639-2020** 模板框架约束，调用 AI 大模型自动撰写和润色预案各章节内容，最终导出为标准格式的 Word 文档（.docx）。

### 1.2 三类预案

| 预案类型 | 英文标识 | 用途 |
|----------|----------|------|
| 综合应急预案 | `comprehensive` | 企业整体应急框架：总则、组织职责、预警响应、后期处置、保障 |
| 专项应急预案 | `special` | 针对特定事故（火灾、触电等）：适用范围、响应启动、处置措施 |
| 现场处置方案 | `onsite` | 一线操作卡片：风险描述、工作职责、操作步骤、注意事项 |

### 1.3 用户画像

- **主要用户**：企业安全管理人员（安全总监、安全员）
- **技能水平**：熟悉安全业务，不要求编程能力
- **使用场景**：一人管理 1~5 家企业，每年编制/修订预案 1~3 次
- **设备**：桌面浏览器（Chrome / Edge），不涉及移动端

---

## 2. 技术架构

### 2.1 架构图

```
┌──────────────────────────────────────────────────────────┐
│                     Nginx (反向代理 + 静态资源)              │
├─────────────────────────┬────────────────────────────────┤
│    前端 (React SPA)     │        后端 (FastAPI)            │
│                         │                                │
│  React 18 + TypeScript  │  REST API (JSON)               │
│  Ant Design 5           │  JWT 认证中间件                  │
│  TipTap 富文本编辑器     │  SQLAlchemy ORM                 │
│  React Router 6         │  Alembic 数据库迁移              │
│                         │  Celery 异步任务 (文档导出)       │
│                         │                                │
│                         │  AI 层：                        │
│                         │  ┌──────────────────────┐      │
│                         │  │ BaseLLMProvider (ABC) │      │
│                         │  ├──────────────────────┤      │
│                         │  │ OpenAI │ 通义 │ 文心 │      │
│                         │  └──────────────────────┘      │
├─────────────────────────┴────────────────────────────────┤
│                    PostgreSQL 15                          │
└──────────────────────────────────────────────────────────┘
```

### 2.2 技术栈明细

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 前端框架 | React | 18.x | SPA 主框架 |
| 前端语言 | TypeScript | 5.x | 类型安全 |
| UI 组件库 | Ant Design | 5.x | 企业级 UI 组件 |
| 富文本编辑器 | TipTap | 2.x | 基于 ProseMirror，支持 Markdown 互转 |
| HTTP 客户端 | Axios | 1.x | API 请求 + 拦截器 |
| 路由 | React Router | 6.x | 前端路由 |
| 状态管理 | React Context + useReducer | — | 全局状态（用户、当前企业） |
| 后端框架 | FastAPI | 0.110+ | 异步 REST API |
| 后端语言 | Python | 3.11+ | — |
| ORM | SQLAlchemy | 2.x | 异步 ORM |
| 数据库迁移 | Alembic | 1.x | Schema 版本管理 |
| 认证 | python-jose + passlib | — | JWT 签发/验证 + bcrypt |
| 异步任务 | Celery + Redis | 5.x | 文档导出等耗时任务 |
| 文档生成 | python-docx | 1.x | .docx 生成 |
| 模板引擎 | Jinja2 | 3.x | 提示词模板 + docx 模板 |
| 加密 | cryptography | 41+ | AES-256 API Key 加密 |
| 数据库 | PostgreSQL | 15+ | 主数据存储 |
| 反向代理 | Nginx | 1.25+ | 静态资源 + API 代理 |

### 2.3 项目目录结构

```
project-root/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 应用入口
│   │   ├── config.py                # 配置管理（环境变量 + .env）
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py              # 依赖注入（get_db, get_current_user）
│   │   │   ├── auth.py              # /api/auth/*
│   │   │   ├── users.py             # /api/users/*
│   │   │   ├── enterprises.py       # /api/enterprises/*
│   │   │   ├── risk_sources.py      # /api/enterprises/{id}/risk-sources/*
│   │   │   ├── resources.py         # /api/enterprises/{id}/resources/*
│   │   │   ├── plans.py             # /api/plans/*
│   │   │   ├── sections.py          # /api/plans/{id}/sections/*
│   │   │   ├── generation.py        # /api/plans/{id}/generate/*
│   │   │   ├── templates.py         # /api/templates/*
│   │   │   ├── versions.py          # /api/plans/{id}/versions/*
│   │   │   └── export.py            # /api/plans/{id}/export
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── enterprise.py
│   │   │   ├── risk_source.py
│   │   │   ├── emergency_resource.py
│   │   │   ├── plan.py
│   │   │   ├── plan_section.py
│   │   │   ├── plan_version.py
│   │   │   ├── plan_template.py
│   │   │   └── ai_config.py
│   │   ├── schemas/                 # Pydantic 请求/响应模型
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── enterprise.py
│   │   │   ├── risk_source.py
│   │   │   ├── resource.py
│   │   │   ├── plan.py
│   │   │   ├── section.py
│   │   │   ├── generation.py
│   │   │   ├── template.py
│   │   │   └── export.py
│   │   ├── services/                # 业务逻辑层
│   │   │   ├── auth_service.py
│   │   │   ├── enterprise_service.py
│   │   │   ├── plan_service.py
│   │   │   ├── generation_service.py
│   │   │   ├── template_service.py
│   │   │   ├── export_service.py
│   │   │   └── version_service.py
│   │   ├── ai/                      # AI 适配层
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # BaseLLMProvider 抽象类
│   │   │   ├── openai_provider.py
│   │   │   ├── qwen_provider.py
│   │   │   ├── wenxin_provider.py
│   │   │   ├── deepseek_provider.py
│   │   │   ├── factory.py           # 模型工厂（根据配置创建实例）
│   │   │   └── prompt_manager.py    # 提示词构建与管理
│   │   ├── core/
│   │   │   ├── security.py          # JWT、加密工具
│   │   │   └── exceptions.py        # 自定义异常
│   │   └── db/
│   │       ├── base.py              # SQLAlchemy Base
│   │       └── session.py           # 异步 session 管理
│   ├── data/
│   │   └── templates/               # 预案模板 JSON 文件
│   │       ├── comprehensive.json   # 综合应急预案
│   │       ├── special.json         # 专项应急预案
│   │       └── onsite.json          # 现场处置方案
│   ├── prompts/                     # AI 提示词模板
│   │   ├── comprehensive/
│   │   ├── special/
│   │   └── onsite/
│   ├── alembic/                     # 数据库迁移
│   ├── tests/
│   ├── requirements.txt
│   └── pyproject.toml
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── main.tsx                 # 入口
│   │   ├── App.tsx                  # 根组件（路由 + Provider）
│   │   ├── routes.tsx               # 路由配置
│   │   ├── layouts/
│   │   │   ├── MainLayout.tsx       # 主布局（侧边栏+顶栏+内容区）
│   │   │   └── AuthLayout.tsx       # 认证页布局
│   │   ├── pages/
│   │   │   ├── Login/
│   │   │   ├── Register/
│   │   │   ├── Dashboard/
│   │   │   ├── Enterprise/
│   │   │   │   ├── EnterpriseList.tsx
│   │   │   │   ├── EnterpriseForm.tsx
│   │   │   │   ├── EnterpriseDetail.tsx
│   │   │   │   ├── RiskSources.tsx
│   │   │   │   └── EmergencyResources.tsx
│   │   │   ├── PlanEditor/
│   │   │   │   ├── PlanList.tsx
│   │   │   │   ├── PlanCreate.tsx
│   │   │   │   ├── PlanEditor.tsx
│   │   │   │   └── ExportPreview.tsx
│   │   │   └── Settings/
│   │   │       ├── Profile.tsx
│   │   │       └── AIModelConfig.tsx
│   │   ├── components/              # 通用组件
│   │   │   ├── SectionTree.tsx      # 章节树
│   │   │   ├── RichTextEditor.tsx   # TipTap 封装
│   │   │   ├── AIGenerateButton.tsx # AI 生成按钮
│   │   │   ├── EnterpriseSwitcher.tsx # 企业切换器
│   │   │   └── ...
│   │   ├── hooks/                   # 自定义 Hooks
│   │   ├── services/                # API 调用层
│   │   │   ├── api.ts               # Axios 实例 + 拦截器
│   │   │   ├── authService.ts
│   │   │   ├── enterpriseService.ts
│   │   │   ├── planService.ts
│   │   │   ├── generationService.ts
│   │   │   └── exportService.ts
│   │   ├── types/                   # TypeScript 类型定义
│   │   ├── utils/
│   │   └── styles/
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── .env.example
└── 功能清单.md
```

---

## 3. 全局约定

### 3.1 API 约定

**基础 URL**：`/api/v1`

**请求格式**：`Content-Type: application/json`（文件上传除外）

**响应格式**：

```json
// 成功
{
  "code": 0,
  "message": "ok",
  "data": { ... }
}

// 列表
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}

// 错误
{
  "code": 40101,
  "message": "无效的访问令牌",
  "detail": null
}
```

**HTTP 状态码约定**：
- `200`：成功
- `201`：创建成功
- `400`：请求参数错误
- `401`：未认证
- `403`：无权限
- `404`：资源不存在
- `422`：参数校验失败（Pydantic）
- `500`：服务器内部错误

**分页参数**（Query String）：`?page=1&page_size=20`，默认 page=1，page_size=20，最大 100。

**认证方式**：所有需认证的接口在 Header 中携带 `Authorization: Bearer <access_token>`。

### 3.2 错误码体系

| 错误码范围 | 含义 |
|-----------|------|
| 0 | 成功 |
| 10001-10099 | 认证相关 |
| 20001-20099 | 企业相关 |
| 30001-30099 | 预案相关 |
| 40001-40099 | AI 生成相关 |
| 50001-50099 | 导出相关 |
| 90001-90099 | 系统通用 |

### 3.3 数据库约定

- 表名：小写蛇形命名，复数形式（`users`, `enterprises`, `plan_projects`）
- 主键：`id`，UUID 类型，Python 侧用 `uuid.uuid4()`
- 时间戳：所有表含 `created_at`、`updated_at`（UTC，`TIMESTAMPTZ`）
- 软删除：核心业务表使用 `deleted_at` 字段，不做物理删除
- JSONB：用于灵活结构（`org_structure`、`snapshot`）
- 索引：所有外键列建索引，高频查询列建复合索引

### 3.4 前端约定

- 组件文件：PascalCase 命名（`EnterpriseList.tsx`）
- Hook 文件：`use` 前缀（`useAuth.ts`）
- Service 文件：`Service` 后缀（`authService.ts`）
- API 调用统一通过 `services/api.ts` 的 Axios 实例，自动处理 Token 注入和刷新
- 页面级组件放 `pages/`，可复用组件放 `components/`
- 每个页面可独立路由，URL 体现层级：`/enterprises/:id/risk-sources`

### 3.5 安全约定

- 用户密码：bcrypt 哈希，cost factor = 12
- API Key：AES-256-CBC 加密存储，密钥从环境变量 `ENCRYPTION_KEY` 获取
- JWT：access_token 2h，refresh_token 7d
- SQL 注入防护：SQLAlchemy 参数化查询
- XSS 防护：React 默认转义 + DOMPurify 清洗富文本
- CORS：仅允许前端域名

---

## 4. 开发环境

### 4.1 Docker Compose 开发环境

```yaml
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: emergency_plan
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev123
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  backend:
    build: ./backend
    command: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ports: ["8000:8000"]
    volumes: ["./backend:/app"]
    depends_on: [db, redis]

  frontend:
    build: ./frontend
    command: npm run dev
    ports: ["5173:5173"]
    volumes: ["./frontend:/app"]
    depends_on: [backend]
```

### 4.2 环境变量

```
# 数据库
DATABASE_URL=postgresql+asyncpg://dev:dev123@localhost:5432/emergency_plan

# JWT
JWT_SECRET_KEY=<generate-random-64-chars>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
REFRESH_TOKEN_EXPIRE_DAYS=7

# 加密
ENCRYPTION_KEY=<32-byte-hex>

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
```

### 4.3 启动命令

```bash
# 初始化
docker compose up -d db redis
cd backend && pip install -r requirements.txt
alembic upgrade head
python -m app.data.seed_templates  # 导入预案模板

# 开发
docker compose up -d
# 后端：http://localhost:8000/docs (Swagger)
# 前端：http://localhost:5173
```

---

## 5. 全局数据模型（ER 概要）

```
users 1──N enterprises
enterprises 1──N risk_sources
enterprises 1──N emergency_resources
enterprises 1──N plan_projects
users 1──N plan_projects
plan_projects 1──N plan_sections
plan_projects 1──N plan_versions
users 1──1 ai_configs
plan_templates (系统级，非用户关联)
```

---

## 6. 路由总表

### 6.1 前端路由

| 路径 | 页面 | 认证 |
|------|------|------|
| `/login` | 登录 | 否 |
| `/register` | 注册 | 否 |
| `/dashboard` | 工作台 | 是 |
| `/enterprises` | 企业列表 | 是 |
| `/enterprises/new` | 新建企业 | 是 |
| `/enterprises/:id` | 企业详情 | 是 |
| `/enterprises/:id/edit` | 编辑企业 | 是 |
| `/enterprises/:id/risk-sources` | 风险源管理 | 是 |
| `/enterprises/:id/resources` | 应急资源管理 | 是 |
| `/plans` | 预案列表 | 是 |
| `/plans/new` | 新建预案 | 是 |
| `/plans/:id/edit` | 预案编辑器 | 是 |
| `/plans/:id/versions` | 版本管理 | 是 |
| `/plans/:id/preview` | 导出预览 | 是 |
| `/settings/profile` | 个人资料 | 是 |
| `/settings/ai-config` | AI 模型配置 | 是 |

### 6.2 后端 API 路由

| 方法 | 路径 | 说明 | 所属 PRD |
|------|------|------|----------|
| POST | `/api/v1/auth/register` | 注册 | PRD-01 |
| POST | `/api/v1/auth/login` | 登录 | PRD-01 |
| POST | `/api/v1/auth/refresh` | 刷新 Token | PRD-01 |
| POST | `/api/v1/auth/logout` | 退出 | PRD-01 |
| GET/PUT | `/api/v1/users/me` | 个人信息 | PRD-01 |
| CRUD | `/api/v1/enterprises` | 企业 CRUD | PRD-02 |
| CRUD | `/api/v1/enterprises/{id}/risk-sources` | 风险源 CRUD | PRD-02 |
| CRUD | `/api/v1/enterprises/{id}/resources` | 应急资源 CRUD | PRD-02 |
| GET | `/api/v1/templates` | 模板列表 | PRD-03 |
| GET | `/api/v1/templates/{id}` | 模板详情 | PRD-03 |
| CRUD | `/api/v1/plans` | 预案项目 CRUD | PRD-05 |
| GET/PUT | `/api/v1/plans/{id}/sections/{key}` | 章节读写 | PRD-05 |
| POST | `/api/v1/plans/{id}/generate/{section_key}` | 单节 AI 生成 | PRD-04 |
| POST | `/api/v1/plans/{id}/generate/batch` | 批量生成 | PRD-04 |
| GET | `/api/v1/plans/{id}/versions` | 版本列表 | PRD-06 |
| GET | `/api/v1/plans/{id}/versions/{vid}` | 版本详情 | PRD-06 |
| POST | `/api/v1/plans/{id}/versions/rollback` | 版本回滚 | PRD-06 |
| GET | `/api/v1/plans/{id}/export/preview` | 导出预览 HTML | PRD-06 |
| POST | `/api/v1/plans/{id}/export/docx` | 导出 .docx | PRD-06 |
| CRUD | `/api/v1/settings/ai-config` | AI 配置 | PRD-04 |

---

## 7. PRD 索引

| 编号 | 模块 | 核心职责 |
|------|------|----------|
| PRD-01 | 用户与权限 | 注册、登录、JWT、个人信息 |
| PRD-02 | 企业管理 | 企业信息、风险源、应急资源、组织架构 |
| PRD-03 | 预案模板管理 | GB/T 29639-2020 模板结构、提示词模板 |
| PRD-04 | AI 生成引擎 | 多模型适配、提示词构建、流式生成、合规检查 |
| PRD-05 | 预案编辑器 | 预案项目 CRUD、章节编辑器、富文本、状态流转 |
| PRD-11 | 风险评估报告 | AI 生成风险评估报告、风险等级矩阵、摘要提取 |
| PRD-12 | 应急资源调查报告 | AI 生成资源调查报告、需求-能力差距分析 |
| PRD-06 | 版本管理与文档导出 | 版本快照/对比/回滚、.docx 公文格式导出 |




