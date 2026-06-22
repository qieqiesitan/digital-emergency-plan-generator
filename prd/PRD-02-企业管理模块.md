# PRD-02：企业管理模块

> **版本**：1.0 | **创建日期**：2026-06-05 | **依赖**：PRD-00, PRD-01

---

## 1. 模块概述

管理企业的安全相关结构化数据，是 AI 生成预案的核心数据源。包含四个子模块：

- **企业基本信息**：名称、地址、行业、规模等
- **组织架构与职责**：应急指挥部及各应急小组
- **风险源管理**：风险识别、评估、管控措施
- **应急资源管理**：内部物资 + 外部救援力量

---

## 2. 数据模型

### 2.1 enterprises 表

```sql
CREATE TABLE enterprises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    address TEXT NOT NULL DEFAULT '''',
    industry VARCHAR(100) NOT NULL DEFAULT '''',
    business_scope TEXT NOT NULL DEFAULT '''',
    employee_count INTEGER,
    building_overview TEXT DEFAULT '''',
    org_structure JSONB NOT NULL DEFAULT ''[]''::jsonb,
    surrounding_info JSONB NOT NULL DEFAULT ''{}''::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_enterprises_user ON enterprises(user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_enterprises_name ON enterprises(name) WHERE deleted_at IS NULL;
```

**org_structure JSONB 结构**：
```json
[
  {
    "group_key": "headquarters",
    "group_name": "应急指挥部",
    "members": [
      {
        "role": "总指挥",
        "name": "张三",
        "position": "总经理",
        "phone": "13800001111"
      },
      {
        "role": "副总指挥",
        "name": "李四",
        "position": "安全副总",
        "phone": "13800002222"
      }
    ]
  },
  {
    "group_key": "rescue",
    "group_name": "抢险救灾组",
    "members": [
      {
        "role": "组长",
        "name": "王五",
        "phone": "13800003333",
        "responsibilities": "负责事故现场的抢险救援工作..."
      }
    ]
  }
]
```

**预置应急小组 key**：`headquarters`(指挥部), `rescue`(抢险救灾), `evacuation`(疏散引导), `medical`(医疗救护), `communication`(通讯联络), `logistics`(后勤保障)

**surrounding_info JSONB 结构**：
```json
{
  "nearby_units": [
    {"name": "XX化工厂", "direction": "东", "distance_m": 500, "main_risk": "火灾爆炸"}
  ],
  "sensitive_targets": [
    {"name": "XX小学", "direction": "南", "distance_m": 300, "type": "学校"}
  ],
  "traffic_info": "西邻G105国道，北靠县道X302"
}
```

### 2.2 risk_sources 表

```sql
CREATE TABLE risk_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    location TEXT NOT NULL DEFAULT '''',
    description TEXT NOT NULL DEFAULT '''',
    likelihood VARCHAR(10) NOT NULL DEFAULT ''中'' CHECK (likelihood IN (''高'', ''中'', ''低'')),
    severity VARCHAR(10) NOT NULL DEFAULT ''中'' CHECK (severity IN (''高'', ''中'', ''低'')),
    risk_level VARCHAR(10) NOT NULL DEFAULT ''中'' CHECK (risk_level IN (''重大'', ''较大'', ''一般'', ''低'')),
    control_measures TEXT NOT NULL DEFAULT '''',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_risk_sources_enterprise ON risk_sources(enterprise_id);
CREATE INDEX idx_risk_sources_category ON risk_sources(enterprise_id, category);
```

**风险等级计算规则**：

|  | 严重性高 | 严重性中 | 严重性低 |
|--|---------|---------|---------|
| 可能性高 | 重大 | 重大 | 较大 |
| 可能性中 | 重大 | 较大 | 一般 |
| 可能性低 | 较大 | 一般 | 低 |

**预置风险类别**：`火灾`、`爆炸`、`触电`、`中毒窒息`、`机械伤害`、`高处坠落`、`物体打击`、`车辆伤害`、`淹溺`、`坍塌`、`锅炉爆炸`、`容器爆炸`、`其他`

### 2.3 emergency_resources 表

```sql
CREATE TABLE emergency_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    specification VARCHAR(200) DEFAULT '''',
    quantity INTEGER NOT NULL DEFAULT 1,
    unit VARCHAR(20) NOT NULL DEFAULT ''个'',
    location TEXT NOT NULL DEFAULT '''',
    responsible_person VARCHAR(100) DEFAULT '''',
    contact_phone VARCHAR(20) DEFAULT '''',
    is_external BOOLEAN NOT NULL DEFAULT FALSE,
    external_address TEXT DEFAULT '''',
    external_distance_km REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_resources_enterprise ON emergency_resources(enterprise_id);
CREATE INDEX idx_resources_category ON emergency_resources(enterprise_id, category);
CREATE INDEX idx_resources_external ON emergency_resources(enterprise_id, is_external);
```

**预置资源类别**：
- 内部资源：`消防设施`、`急救物资`、`防护装备`、`通讯设备`、`照明设备`、`破拆工具`、`侦检设备`、`堵漏器材`
- 外部资源：`消防队`、`医院`、`公安机关`、`安监部门`、`环保部门`

### 2.4 Pydantic Schema

```python
# 企业
class EnterpriseCreate(BaseModel):
    name: str
    address: str = ""
    industry: str = ""
    business_scope: str = ""
    employee_count: int | None = None
    building_overview: str = ""

class EnterpriseUpdate(EnterpriseCreate):
    pass

class EnterpriseResponse(BaseModel):
    id: UUID
    name: str
    address: str
    industry: str
    business_scope: str
    employee_count: int | None
    building_overview: str | None
    org_structure: list[OrgGroup]
    surrounding_info: SurroundingInfo | None
    risk_sources_count: int = 0
    resources_count: int = 0
    plans_count: int = 0
    created_at: datetime
    updated_at: datetime

# 组织架构
class OrgMember(BaseModel):
    role: str          # 职务：总指挥/组长/成员
    name: str          # 姓名
    position: str = "" # 公司职位
    phone: str = ""
    responsibilities: str = ""

class OrgGroup(BaseModel):
    group_key: str     # headquarters/rescue/evacuation/medical/communication/logistics
    group_name: str
    members: list[OrgMember] = []

class EnterpriseOrgUpdate(BaseModel):
    org_structure: list[OrgGroup]

# 周边环境
class NearbyUnit(BaseModel):
    name: str
    direction: str    # 东/南/西/北/东南...
    distance_m: int
    main_risk: str

class SensitiveTarget(BaseModel):
    name: str
    direction: str
    distance_m: int
    type: str         # 学校/医院/居民区/水源地

class SurroundingInfo(BaseModel):
    nearby_units: list[NearbyUnit] = []
    sensitive_targets: list[SensitiveTarget] = []
    traffic_info: str = ""

# 风险源
class RiskSourceCreate(BaseModel):
    category: str
    name: str
    location: str = ""
    description: str = ""
    likelihood: Literal["高", "中", "低"] = "中"
    severity: Literal["高", "中", "低"] = "中"
    control_measures: str = ""

class RiskSourceUpdate(RiskSourceCreate):
    pass

class RiskSourceResponse(BaseModel):
    id: UUID
    enterprise_id: UUID
    category: str
    name: str
    location: str
    description: str
    likelihood: str
    severity: str
    risk_level: str
    control_measures: str
    sort_order: int
    created_at: datetime

# 应急资源
class EmergencyResourceCreate(BaseModel):
    category: str
    name: str
    specification: str = ""
    quantity: int = 1
    unit: str = "个"
    location: str = ""
    responsible_person: str = ""
    contact_phone: str = ""
    is_external: bool = False
    external_address: str = ""
    external_distance_km: float | None = None

class EmergencyResourceUpdate(EmergencyResourceCreate):
    pass

class EmergencyResourceResponse(BaseModel):
    id: UUID
    enterprise_id: UUID
    category: str
    name: str
    specification: str
    quantity: int
    unit: str
    location: str
    responsible_person: str
    contact_phone: str
    is_external: bool
    external_address: str
    external_distance_km: float | None
    created_at: datetime
```

---

## 3. API 接口

### 3.1 企业 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/enterprises` | 企业列表（分页、搜索、筛选） |
| POST | `/api/v1/enterprises` | 创建企业 |
| GET | `/api/v1/enterprises/{id}` | 企业详情 |
| PUT | `/api/v1/enterprises/{id}` | 更新企业基本信息 |
| DELETE | `/api/v1/enterprises/{id}` | 删除企业（级联所有关联数据） |

**GET /enterprises 查询参数**：
- `page` (int, default=1)
- `page_size` (int, default=20)
- `search` (str, 按名称模糊搜索)
- `industry` (str, 按行业筛选)

**GET /enterprises/{id} 响应**：
```json
{
  "code": 0,
  "data": {
    "id": "uuid",
    "name": "XX化工有限公司",
    "address": "XX省XX市XX区XX路100号",
    "industry": "危险化学品",
    "business_scope": "化工产品生产销售",
    "employee_count": 200,
    "building_overview": "厂区占地50亩，含生产车间3栋、仓库2栋、办公楼1栋",
    "org_structure": [...],
    "surrounding_info": {...},
    "risk_sources_count": 8,
    "resources_count": 25,
    "plans_count": 3,
    "created_at": "...",
    "updated_at": "..."
  }
}
```

**安全约束**：所有企业接口仅返回 `user_id` 匹配当前用户的数据。访问非本人企业返回 404。

### 3.2 组织架构

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/enterprises/{id}/org-structure` | 获取组织架构 |
| PUT | `/api/v1/enterprises/{id}/org-structure` | 更新组织架构（全量替换） |

**GET 响应体**：`{ "data": [OrgGroup, ...] }`

**PUT 请求体**：`[OrgGroup, ...]`

**校验规则**：
- group_key 必须在预置列表中
- 每个 group 至少 1 名成员
- 指挥部必须有"总指挥"角色
- 手机号格式校验（1 开头 11 位数字，选填）

### 3.3 风险源 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/enterprises/{id}/risk-sources` | 风险源列表 |
| POST | `/api/v1/enterprises/{id}/risk-sources` | 新增风险源 |
| GET | `/api/v1/enterprises/{id}/risk-sources/{rsid}` | 风险源详情 |
| PUT | `/api/v1/enterprises/{id}/risk-sources/{rsid}` | 更新风险源 |
| DELETE | `/api/v1/enterprises/{id}/risk-sources/{rsid}` | 删除风险源 |

**POST 处理逻辑**：
1. 添加 `enterprise_id`
2. 根据 likelihood × severity 自动计算 risk_level（后端的矩阵计算逻辑）
3. 自动设置 sort_order = max(sort_order) + 1

**GET 查询参数**：
- `category`：按类别筛选
- `risk_level`：按等级筛选（重大/较大/一般/低）
- `sort_by`：排序字段，默认 `risk_level DESC, sort_order ASC`

**DELETE 副作用**：如该风险源已被预案引用，删除前需检查并提示用户。被引用时不阻止删除（预案章节内容保留历史文字），但前端提示"有 N 个预案引用了此风险源"。

### 3.4 应急资源 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/enterprises/{id}/resources` | 资源列表 |
| POST | `/api/v1/enterprises/{id}/resources` | 新增资源 |
| GET | `/api/v1/enterprises/{id}/resources/{rid}` | 资源详情 |
| PUT | `/api/v1/enterprises/{id}/resources/{rid}` | 更新资源 |
| DELETE | `/api/v1/enterprises/{id}/resources/{rid}` | 删除资源 |

**GET 查询参数**：
- `category`：按类别筛选
- `is_external`：内部/外部筛选
- `search`：按名称或位置搜索

### 3.5 周边环境

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/enterprises/{id}/surrounding` | 获取周边信息 |
| PUT | `/api/v1/enterprises/{id}/surrounding` | 更新周边信息 |

**请求体**：`SurroundingInfo` 对象
**存储**：序列化为 JSONB 存入 `enterprises.surrounding_info`

---

## 4. 前端页面

### 4.1 企业列表页

- 顶部：搜索框 + 行业下拉筛选 + "新建企业"按钮
- 表格列：企业名称、行业、员工数、风险源数、预案数、更新时间
- 操作列：编辑、删除
- 点击企业名称 → 进入企业详情

### 4.2 新建/编辑企业页

- 表单字段：企业名称*、地址、行业（下拉+自定义输入）、经营范围、员工人数、建筑概况
- * 号标记必填字段
- 保存后跳转到企业详情页
- 编辑页加载时回填已有数据

### 4.3 企业详情页

- 使用 Ant Design Tabs 组件
- 标签页：基本信息 | 组织架构 | 风险源 | 应急资源 | 周边环境
- 基本信息 Tab：数据展示 + "编辑"按钮跳转编辑页
- 每个 Tab 右上角显示条目数量

### 4.4 组织架构 Tab

- 按预置小组分组显示
- 每组以折叠面板（Collapse）展示
- 成员以表格展示：职务、姓名、公司职位、电话、职责
- "编辑组织架构"按钮 → 弹窗（Modal）编辑
- 编辑弹窗：可增删小组和成员，支持拖拽排序（可选）

### 4.5 风险源 Tab

- 顶部筛选：风险类别（Select 多选）、风险等级（Select）
- 表格列：类别、名称、位置、可能性、严重性、风险等级（彩色标签）、操作
- 风险等级标签颜色：重大=红色、较大=橙色、一般=黄色、低=蓝色
- "新增风险源"按钮 → 弹窗表单
- 编辑/删除按钮逐行提供
- 危险源默认按风险等级从高到低排列

### 4.6 应急资源 Tab

- 顶部：类别筛选 + 内部/外部切换（Radio Group）+ 搜索框
- 表格列：类别、名称、规格、数量、存放位置/地址、责任人、电话、操作
- 外部资源显示"距离"列替代"存放位置"
- "新增资源"按钮 → 弹窗表单
- 表单中"外部资源"开关控制显示字段

### 4.7 周边环境 Tab

- 三个子区域：周边单位、敏感目标、交通状况
- 周边单位/敏感目标以卡片列表展示
- "编辑"按钮 → 弹窗编辑

---

## 5. 业务逻辑

### 5.1 风险等级自动计算

```python
RISK_MATRIX = {
    ("高", "高"): "重大",
    ("高", "中"): "重大",
    ("中", "高"): "重大",
    ("高", "低"): "较大",
    ("低", "高"): "较大",
    ("中", "中"): "较大",
    ("中", "低"): "一般",
    ("低", "中"): "一般",
    ("低", "低"): "低",
}

def calculate_risk_level(likelihood: str, severity: str) -> str:
    return RISK_MATRIX.get((likelihood, severity), "一般")
```

### 5.2 关联预案影响检测

在企业数据变更时（企业名称、风险源删除等），需在响应中提示关联影响：

```json
// 风险源删除成功，但有预案引用时的响应
{
  "code": 0,
  "message": "已删除",
  "data": {
    "affected_plans": 2,
    "warning": "有 2 个预案引用了此风险源，相关章节内容将保留，建议手动更新"
  }
}
```

### 5.3 企业数据导出为 AI 上下文

`EnterpriseService.export_as_context(enterprise_id)` 方法：将企业所有结构化数据格式化为 Markdown 文本，供 AI 生成章节时注入提示词。各 PRD 模块在提示词构建时调用此方法。

---

## 6. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC11 | 创建企业成功，字段校验生效 | 自动化：POST /enterprises → 201 |
| AC12 | 企业列表仅显示当前用户的 | 自动化：用户 A 创建企业 → 用户 B GET 列表 → 不包含 A 的企业 |
| AC13 | 访问他人企业返回 404 | 自动化：用户 A 企业 ID → 用户 B GET → 404 |
| AC14 | 风险源创建后风险等级自动计算 | 自动化：创建 高+高 → risk_level="重大" |
| AC15 | 组织架构校验生效 | 自动化：清空指挥部成员 PUT → 422 |
| AC16 | 应急资源内/外部筛选正常 | 自动化：GET ?is_external=true → 仅返回外部资源 |
| AC17 | 删除企业级联删除风险源和资源 | 自动化：企业含 3 风险源 → 删除企业 → 查询风险源 → 空 |
| AC18 | 风险源按风险等级排序 | 自动化：GET → items 中 risk_level 降序排列 |
| AC19 | 周边环境 JSONB 读写正确 | 自动化：PUT → GET → 数据一致 |
| AC20 | 企业选择器正常切换 | E2E：切换企业后预案列表更新 |
