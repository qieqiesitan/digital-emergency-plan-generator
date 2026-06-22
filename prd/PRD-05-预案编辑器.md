# PRD-05：预案编辑器

> **版本**：1.0 | **创建日期**：2026-06-05 | **依赖**：PRD-00, PRD-01, PRD-02, PRD-03, PRD-04

---

## 1. 模块概述

预案编辑器是用户日常工作的核心界面，提供预案项目管理和章节编辑功能。用户在此完成从新建预案到最终成稿的全流程操作。

**核心流程**：新建预案 → 绑定企业 + 模板 → 初始化章节结构 → 逐章编辑/AI 生成 → 导出

---

## 2. 数据模型

### 2.1 plan_projects 表

```sql
CREATE TABLE plan_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES plan_templates(id),
    plan_type VARCHAR(20) NOT NULL CHECK (plan_type IN (''comprehensive'', ''special'', ''onsite'')),
    title VARCHAR(200) NOT NULL,
    accident_type VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT ''draft''
        CHECK (status IN (''draft'', ''generating'', ''completed'')),
    current_version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_plans_user ON plan_projects(user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_plans_enterprise ON plan_projects(enterprise_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_plans_type ON plan_projects(user_id, plan_type) WHERE deleted_at IS NULL;
```

**plan_type 与 accident_type 的关系**：
- `comprehensive`：`accident_type` 为 NULL
- `special`：`accident_type` 必填，从企业的风险源类别中选择
- `onsite`：`accident_type` 必填，同上

### 2.2 plan_sections 表

```sql
CREATE TABLE plan_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_project_id UUID NOT NULL REFERENCES plan_projects(id) ON DELETE CASCADE,
    section_key VARCHAR(100) NOT NULL,
    title VARCHAR(200) NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL DEFAULT '''',
    ai_generated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(plan_project_id, section_key)
);

CREATE INDEX idx_sections_plan ON plan_sections(plan_project_id);
```

**章节初始化规则**：创建预案时，从绑定的模板 `structure` 递归遍历所有章节节点，为每个节点创建一条 `plan_sections` 记录。`content` 初始为空字符串。

**content 存储格式**：Markdown。前端 TipTap 编辑器读写时进行 HTML ↔ Markdown 转换。

### 2.3 Pydantic Schema

```python
class PlanCreate(BaseModel):
    enterprise_id: UUID
    plan_type: Literal["comprehensive", "special", "onsite"]
    title: str = Field(..., max_length=200)
    accident_type: str | None = None   # 专项/现场必填

class PlanUpdate(BaseModel):
    title: str | None = None

class PlanResponse(BaseModel):
    id: UUID
    enterprise_id: UUID
    enterprise_name: str
    plan_type: str
    title: str
    accident_type: str | None
    status: str
    current_version: int
    sections_count: int
    completed_sections: int
    created_at: datetime
    updated_at: datetime

class PlanDetailResponse(PlanResponse):
    sections: list[SectionResponse]

class SectionResponse(BaseModel):
    id: UUID
    section_key: str
    title: str
    level: int
    sort_order: int
    content: str
    ai_generated: bool
    updated_at: datetime

class SectionUpdate(BaseModel):
    content: str
```

---

## 3. API 接口

### 3.1 预案项目 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/plans` | 预案列表 |
| POST | `/api/v1/plans` | 新建预案 |
| GET | `/api/v1/plans/{id}` | 预案详情（含章节列表） |
| PUT | `/api/v1/plans/{id}` | 更新预案标题 |
| DELETE | `/api/v1/plans/{id}` | 删除预案 |
| POST | `/api/v1/plans/{id}/duplicate` | 复制预案 (Phase 2) |

**GET /plans 查询参数**：
- `page`, `page_size`
- `enterprise_id`（必填，筛选当前企业的预案）
- `plan_type`（comprehensive/special/onsite）
- `status`（draft/completed）
- `search`（按标题搜索）

**POST /plans 处理逻辑**：
```python
async def create_plan(request: PlanCreate, user: User, db: AsyncSession):
    # 1. 校验企业归属
    enterprise = await db.get(Enterprise, request.enterprise_id)
    if enterprise.user_id != user.id:
        raise HTTPException(404)

    # 2. 获取对应模板
    query = select(PlanTemplate).where(
        PlanTemplate.plan_type == request.plan_type,
        PlanTemplate.is_active == True
    )
    template = (await db.execute(query)).scalar_one()

    # 3. 校验 accident_type
    if request.plan_type in ("special", "onsite") and not request.accident_type:
        raise HTTPException(422, "专项预案和现场处置方案必须指定事故类型")

    # 4. 创建预案项目
    plan = PlanProject(
        user_id=user.id,
        enterprise_id=request.enterprise_id,
        template_id=template.id,
        plan_type=request.plan_type,
        title=request.title,
        accident_type=request.accident_type,
        status="draft",
    )
    db.add(plan)
    await db.flush()

    # 5. 递归遍历模板 structure，初始化所有章节
    sections = []
    order_counter = [0]
    self._create_sections_from_template(
        template.structure, plan.id, sections, order_counter
    )
    db.add_all(sections)
    await db.commit()

    return plan
```

### 3.2 章节读写

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/plans/{id}/sections/{key}` | 获取章节内容 |
| PUT | `/api/v1/plans/{id}/sections/{key}` | 更新章节内容 |
| GET | `/api/v1/plans/{id}/sections` | 获取所有章节列表 |

**PUT 请求体**：
```json
{
  "content": "# 编制目的\n\n为建立健全..."
}
```

**保存后副作用**：
- 更新 `plan_projects.updated_at`
- 检测所有必填章节是否已填写，更新 `status` 为 `completed`
- 触发自动版本快照（如已开启，见 PRD-06）

### 3.3 状态自动判定

```python
async def update_plan_status(plan_id: UUID, db: AsyncSession):
    """根据章节完成情况自动更新预案状态"""
    plan = await db.get(PlanProject, plan_id)

    # 获取 template 中所有 required=true 的章节 key
    template = await db.get(PlanTemplate, plan.template_id)
    required_keys = self._get_required_section_keys(template.structure)

    # 查询已填写的章节数
    result = await db.execute(
        select(func.count(PlanSection.id)).where(
            PlanSection.plan_project_id == plan_id,
            PlanSection.section_key.in_(required_keys),
            func.length(PlanSection.content) > 0,
        )
    )
    filled_count = result.scalar()

    if filled_count >= len(required_keys):
        plan.status = "completed"
    else:
        plan.status = "draft"

    await db.commit()
```

---

## 4. 前端页面

### 4.1 预案列表页

- 顶部：企业选择器 + 搜索框 + "新建预案"按钮
- 筛选：预案类型（Tabs：全部/综合预案/专项预案/现场处置方案）、状态（Radio）
- 卡片列表或表格：
  - 每条显示：标题、类型（彩色 Tag）、事故类型（专项/现场）、状态（Tag）、章节进度（xx/xx）、更新时间
  - 操作：编辑、删除、复制
- 点击卡片 → 进入编辑器

### 4.2 新建预案向导

- **步骤 1**：选择预案类型（三个大卡片：综合/专项/现场处置）
- **步骤 2（专项/现场处置）**：选择事故类型
  - 下拉列表来自当前企业的风险源类别（去重）
  - 提示："仅显示当前企业已有的风险源类别"
  - 或允许手动输入新的事故类型
- **步骤 3**：填写预案标题
  - 默认标题：「企业名称-预案类型名称」，可修改
- **步骤 4**：确认创建 → 跳转编辑器

### 4.3 预案编辑器（核心页面）

布局：两栏结构

**左侧面板（宽度 280px，可折叠）**：
- 预案标题（可编辑）+ 状态 Tag
- 章节树：递归渲染树形结构，缩进表示层级
  - 每个章节节点显示标题
  - 状态图标：✏️ 已填写 / ⚪ 未填写（必填章显示红点）
  - AI 可生成的章节旁显示 🤖 小图标
  - 当前选中章节高亮
  - 点击切换编辑目标

**右侧编辑区**：
- 顶部工具栏：当前章节标题、字数统计、"AI 生成"按钮（仅 ai_generatable 的章节显示）
- 富文本编辑器（TipTap）：
  - 工具栏：加粗、斜体、标题（H1-H3）、无序列表、有序列表、缩进、表格、撤销、重做
  - 支持粘贴纯文本和 Markdown
  - 内容变更 3 秒后自动保存（debounce），显示"已保存"或"保存中..."
- AI 生成状态：生成中时编辑器只读，实时显示流式内容

**编辑器状态流转**：
```
草稿 ──→ 编辑完成（所有必填章已填）──→ 已完成
  │                                      │
  └──── 修改已有内容 ────→ 草稿 ←────────┘
```

### 4.4 自动保存机制

```typescript
// hooks/useAutoSave.ts
function useAutoSave(planId: string, sectionKey: string, content: string) {
  const saveStatus = useRef<''saved'' | ''saving'' | ''unsaved''>(''saved'');

  useEffect(() => {
    if (content === lastSavedContent.current) return;
    saveStatus.current = ''unsaved'';

    const timer = setTimeout(async () => {
      saveStatus.current = ''saving'';
      try {
        await planService.updateSection(planId, sectionKey, { content });
        lastSavedContent.current = content;
        saveStatus.current = ''saved'';
      } catch {
        saveStatus.current = ''unsaved'';
      }
    }, 3000);

    return () => clearTimeout(timer);
  }, [content]);

  return saveStatus;
}
```

---

## 5. 业务逻辑

### 5.1 章节初始化

```python
def _create_sections_from_template(
    nodes: list[dict],
    plan_id: UUID,
    sections: list,
    order: list[int],
    parent_key: str | None = None
):
    """递归遍历模板章节结构，创建 plan_sections"""
    for node in nodes:
        order[0] += 1
        section = PlanSection(
            plan_project_id=plan_id,
            section_key=node["key"],
            title=node["title"],
            level=node["level"],
            sort_order=order[0],
            content="",
        )
        sections.append(section)

        if node.get("subsections"):
            self._create_sections_from_template(
                node["subsections"], plan_id, sections, order, node["key"]
            )
```

### 5.2 auto_fill 章节处理

```python
async def get_section_content(self, plan_id: UUID, section_key: str) -> str:
    """获取章节内容时，检查是否需要自动填充"""
    section = await self.get_section(plan_id, section_key)
    plan = await self.get_plan(plan_id)

    # 获取模板中的 auto_fill 配置
    template_section = await self.template_service.get_section(plan.plan_type, section_key)

    if template_section.get("auto_fill"):
        enterprise = await self.enterprise_service.get(plan.enterprise_id)
        source = template_section["auto_fill_source"]
        return self._auto_fill_content(source, enterprise, section_key)

    return section.content
```

---

## 6. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC38 | 创建综合预案成功 | 自动化：POST /plans → 201，章节已初始化 |
| AC39 | 创建专项预案需绑定事故类型 | 自动化：POST /plans type=special accident_type=null → 422 |
| AC40 | 预案列表按企业筛选 | 自动化：GET /plans?enterprise_id=X → 仅返回该企业的 |
| AC41 | 章节内容保存 | 自动化：PUT /sections/{key} → 200 → GET 一致 |
| AC42 | 必填章节全部填写后状态变为 completed | 自动化：填完所有 required 章节 → GET /plans/{id} status=completed |
| AC43 | 章节树正确渲染 | E2E：进入编辑器 → 左侧章节树与模板结构一致 |
| AC44 | 自动保存 | E2E：修改内容 → 等待 3s → 数据库 content 已更新 |
| AC45 | 复制预案 | 自动化：POST /duplicate → 新预案，章节数一致 |
| AC46 | 删除预案级联删除章节 | 自动化：DELETE → 查询 sections → 空 |
| AC47 | 章节编辑器 AI 生成状态同步 | E2E：生成完成后 content 正确保存 |
