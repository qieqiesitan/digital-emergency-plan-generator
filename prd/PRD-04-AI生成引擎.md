# PRD-04：AI 生成引擎

> **版本**：1.0 | **创建日期**：2026-06-05 | **依赖**：PRD-00, PRD-01, PRD-03

---

## 1. 模块概述

AI 生成引擎是整个系统的核心差异化模块，负责调用大语言模型自动撰写预案各章节内容。采用**适配器模式**抽象多模型差异，用户自行配置 API Key，系统通过 SS E 流式输出生成内容到前端编辑器。

**核心能力**：
- 多模型适配（OpenAI / 通义千问 / 文心一言 / DeepSeek）
- 提示词动态构建（系统提示词 + 章节提示词 + 企业数据上下文）
- SSE 流式输出（实时显示生成内容）
- 单章节生成 + 批量生成
- 内容合规检查

---

## 2. 数据模型

### 2.1 ai_configs 表

```sql
CREATE TABLE ai_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(30) NOT NULL CHECK (provider IN (''openai'', ''qwen'', ''wenxin'', ''deepseek'')),
    api_key_encrypted BYTEA NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    base_url VARCHAR(500),
    temperature REAL DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 4096,
    top_p REAL DEFAULT 1.0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_test_at TIMESTAMPTZ,
    last_test_result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**加密存储**：`api_key_encrypted` 使用 AES-256-CBC 加密，加密密钥来自环境变量 `ENCRYPTION_KEY`（32 字节 hex）。

### 2.2 模型默认配置

| provider | 默认 model_name | 默认 base_url |
|----------|----------------|---------------|
| openai | gpt-4o | https://api.openai.com/v1 |
| qwen | qwen-turbo | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| wenxin | ernie-4.0-8k | https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat |
| deepseek | deepseek-chat | https://api.deepseek.com/v1 |

### 2.3 generation_logs 表（Phase 2）

```sql
CREATE TABLE generation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    plan_id UUID NOT NULL REFERENCES plan_projects(id),
    section_key VARCHAR(100) NOT NULL,
    provider VARCHAR(30) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    prompt_summary TEXT,
    tokens_used INTEGER,
    duration_ms INTEGER,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.4 Pydantic Schema

```python
class AIConfigCreate(BaseModel):
    provider: Literal["openai", "qwen", "wenxin", "deepseek"]
    api_key: str                          # 明文传入，后端加密存储
    model_name: str
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0

class AIConfigUpdate(BaseModel):
    provider: Literal["openai", "qwen", "wenxin", "deepseek"] | None = None
    api_key: str | None = None
    model_name: str | None = None
    base_url: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None

class AIConfigResponse(BaseModel):
    id: UUID
    provider: str
    model_name: str
    base_url: str | None
    temperature: float
    max_tokens: int
    is_active: bool
    last_test_at: datetime | None
    # api_key 不返回给前端

class AITestRequest(BaseModel):
    """测试连接时的临时参数，不需要保存"""
    provider: Literal["openai", "qwen", "wenxin", "deepseek"]
    api_key: str
    model_name: str
    base_url: str | None = None

class GenerateRequest(BaseModel):
    section_key: str
    custom_instruction: str | None = None  # 用户额外指令

class GenerateBatchRequest(BaseModel):
    section_keys: list[str] | None = None  # None = 所有可生成章节
```

---

## 3. AI 适配层设计

### 3.1 抽象基类

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str

@dataclass
class LLMConfig:
    api_key: str
    model_name: str
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0

class BaseLLMProvider(ABC):
    """LLM 适配器抽象基类"""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def generate(self, messages: list[LLMMessage]) -> str:
        """非流式生成，返回完整文本"""
        ...

    @abstractmethod
    async def generate_stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        """流式生成，每次 yield 一块文本增量"""
        ...

    @abstractmethod
    async def test_connection(self) -> dict:
        """测试连接，返回 {"ok": true, "model": "gpt-4o"} 或 {"ok": false, "error": "..."}"""
        ...
```

### 3.2 OpenAI Provider 实现示例

```python
from openai import AsyncOpenAI

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url or "https://api.openai.com/v1"
        )

    async def generate(self, messages: list[LLMMessage]) -> str:
        response = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            top_p=self.config.top_p,
        )
        return response.choices[0].message.content or ""

    async def generate_stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def test_connection(self) -> dict:
        try:
            response = await self.client.models.list()
            return {"ok": True, "models": len(response.data)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
```

### 3.3 Provider Factory

```python
class LLMFactory:
    _providers = {
        "openai": OpenAIProvider,
        "qwen": QwenProvider,
        "wenxin": WenxinProvider,
        "deepseek": DeepSeekProvider,
    }

    @classmethod
    def create(cls, provider_name: str, config: LLMConfig) -> BaseLLMProvider:
        provider_cls = cls._providers.get(provider_name)
        if not provider_cls:
            raise ValueError(f"不支持的模型提供商: {provider_name}")
        return provider_cls(config)
```

### 3.4 通义千问与文心一言适配要点

- **通义千问**：使用 OpenAI 兼容模式，`base_url` 设为 DashScope 兼容端点，实现同 OpenAI 接口
- **文心一言**：需先调用 access_token 接口获取临时 token，再调用聊天接口；流式输出格式与 OpenAI 不同，需适配
- **DeepSeek**：完全兼容 OpenAI API，仅需修改 `base_url`

---

## 4. 提示词构建器

### 4.1 PromptBuilder

```python
from jinja2 import Environment, BaseLoader

class PromptBuilder:
    SYSTEM_PROMPT = """你是一位持有国家注册安全工程师资格的专业应急预案编制专家..."""

    def __init__(self, template_service, enterprise_service):
        self.template_service = template_service
        self.enterprise_service = enterprise_service
        self.jinja = Environment(loader=BaseLoader())

    async def build_messages(
        self,
        plan_id: UUID,
        section_key: str,
        custom_instruction: str | None = None
    ) -> list[LLMMessage]:
        """构建 AI 调用的 message 列表"""

        # 1. 获取预案信息
        plan = await self.plan_service.get(plan_id)
        enterprise = await self.enterprise_service.get(plan.enterprise_id)

        # 2. 获取模板中的章节定义和提示词模板
        section_template = await self.template_service.get_section(plan.plan_type, section_key)

        # 3. 构建企业数据上下文
        enterprise_context = await self.enterprise_service.export_as_context(
            plan.enterprise_id,
            dependencies=section_template.get("data_dependencies", [])
        )

        # 4. 渲染章节提示词
        prompt_template = section_template.get("prompt_template", "")
        variables = {
            "enterprise": enterprise,
            "enterprise_context": enterprise_context,
            "section": section_template,
            "custom_instruction": custom_instruction or "",
        }
        user_prompt = self.jinja.from_string(prompt_template).render(**variables)

        if custom_instruction:
            user_prompt += f"\n\n用户补充要求：{custom_instruction}"

        return [
            LLMMessage(role="system", content=self.SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_prompt),
        ]
```

### 4.2 变量上下文注入规则

| data_dependencies 值 | 注入内容 |
|---------------------|----------|
| `"enterprise.*"` | 企业全部基本信息 |
| `"risk_sources"` | 所有风险源列表（含等级、管控措施） |
| `"risk_sources.{category}"` | 仅某类风险源（如专项预案只注入相关事故类型） |
| `"resources"` | 所有应急资源汇总 |
| `"org_structure"` | 组织架构表 |
| `"surrounding"` | 周边环境信息 |
| `"enterprise_context"` | 完整上下文（以上全部） |

---

## 5. API 接口

### 5.1 AI 配置 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/settings/ai-config` | 获取当前用户的 AI 配置 |
| PUT | `/api/v1/settings/ai-config` | 创建或更新 AI 配置（upsert） |
| DELETE | `/api/v1/settings/ai-config` | 删除 AI 配置 |
| POST | `/api/v1/settings/ai-config/test` | 测试模型连接 |

**PUT 请求体**：`AIConfigCreate`
**POST /test 请求体**：`AITestRequest`

**测试连接响应**：
```json
// 成功
{ "code": 0, "data": { "ok": true, "detail": "连接成功，模型: gpt-4o" } }

// 失败
{ "code": 0, "data": { "ok": false, "detail": "401 Unauthorized: API Key 无效" } }
```

### 5.2 单章节 AI 生成

```
POST /api/v1/plans/{plan_id}/generate/{section_key}
Authorization: Bearer <access_token>
```

**请求体（可选）**：
```json
{
  "custom_instruction": "请特别强调夜间作业的风险"
}
```

**处理流程**：
1. 检验用户是否有此预案的权限
2. 检查用户是否配置了活跃的 AI 配置，未配置返回 `40001`
3. 检查章节是否 `ai_generatable = true`，否则返回 `40002`
4. 获取或创建该章节记录（`plan_sections`）
5. 调用 `PromptBuilder.build_messages()`
6. 调用 `LLMProvider.generate_stream()`
7. 通过 SSE 流式输出
8. 生成完成后将内容保存到 `plan_sections.content`

**SSE 响应格式**：
```
data: {"type": "chunk", "content": "为建立健全..."}

data: {"type": "chunk", "content": "生产安全事故..."}

data: {"type": "done", "content": "全文内容", "tokens_used": 450}

data: {"type": "error", "message": "API 调用超时"}
```

**错误响应（非流式）**：
- `40001`：未配置 AI 模型
- `40002`：此章节不支持 AI 生成
- `40003`：AI 服务调用失败（API Key 无效、余额不足等）
- `40004`：生成超时（60s）

### 5.3 批量生成

```
POST /api/v1/plans/{plan_id}/generate/batch
Authorization: Bearer <access_token>
```

**请求体**：
```json
{
  "section_keys": ["purpose", "basis", "scope"]  // null = 所有可生成章节
}
```

**处理流程**：
1. 解析 `section_keys`，如果为 null，则从模板获取所有 `ai_generatable=true` 的章节
2. 按 `sort_order` 排序
3. 依次生成每个章节（非流式），或逐个流式推送进度
4. 通过 SSE 推送进度

**SSE 进度格式**：
```
data: {"type": "progress", "current": 3, "total": 15, "section_key": "scope"}

data: {"type": "section_done", "section_key": "scope", "content": "..."}

data: {"type": "batch_done", "completed": 14, "failed": 1}
```

### 5.4 停止生成

```
POST /api/v1/plans/{plan_id}/generate/stop
```

取消当前正在进行的生成任务（通过 Redis 信号或 asyncio.Event）。

---

## 6. 前端 SSE 消费

```typescript
// services/generationService.ts
export async function generateSection(
  planId: string,
  sectionKey: string,
  customInstruction?: string,
  onChunk: (text: string) => void,
  onDone: (fullText: string) => void,
  onError: (error: string) => void
): Promise<void> {
  const token = localStorage.getItem(''access_token'');
  const response = await fetch(
    `/api/v1/plans/${planId}/generate/${sectionKey}`,
    {
      method: ''POST'',
      headers: {
        ''Content-Type'': ''application/json'',
        ''Authorization'': `Bearer ${token}`,
      },
      body: JSON.stringify({ custom_instruction: customInstruction }),
    }
  );

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let fullText = '''';
  let buffer = '''';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split(''\n'');
    buffer = lines.pop() || '''';

    for (const line of lines) {
      if (line.startsWith(''data: '')) {
        const data = JSON.parse(line.slice(6));
        if (data.type === ''chunk'') {
          fullText += data.content;
          onChunk(data.content);
        } else if (data.type === ''done'') {
          onDone(fullText);
        } else if (data.type === ''error'') {
          onError(data.message);
        }
      }
    }
  }
}
```

---

## 7. 生成按钮与状态管理（前端）

### 7.1 AIGenerateButton 组件

```
属性：
- sectionKey: string
- planId: string
- onContentUpdate: (content: string) => void

状态：
- idle: 显示"AI 生成"按钮
- generating: 显示旋转动画 + "生成中..." 文字，按钮不可点击
- done: 闪烁绿色勾 1 秒后回到 idle
- error: 显示错误信息，可点击重试
```

### 7.2 流式更新到编辑器

生成过程中，每个 SSE chunk 到达时，通过 `onContentUpdate` 回调追加到 TipTap 编辑器末尾，用户可实时看到内容逐字出现。

---

## 8. 合规检查（Phase 2）

### 8.1 检查逻辑

生成完成后，对章节内容做规则检查：

```python
async def check_compliance(self, section_key: str, content: str) -> list[str]:
    """
    检查生成的章节内容是否符合 GB/T 要求
    返回缺失的要点列表
    """
    section_template = await self.template_service.get_section(plan_type, section_key)
    gb_requirements = self._parse_gb_keywords(section_template.get("gb_requirement", ""))

    missing = []
    for keyword in gb_requirements:
        if keyword not in content:
            missing.append(keyword)

    return missing
```

### 8.2 前端合规提示

生成完成后，如有缺失要点，前端在章节编辑器中显示黄色 Alert：
"生成内容可能未覆盖以下要点：编制依据、应急预案体系。建议手动补充或重新生成。"

---

## 9. 错误处理与重试

| 错误场景 | 处理方式 |
|----------|----------|
| API Key 无效 | 返回 40003，前端提示跳转 AI 配置页 |
| 余额不足 | 返回 40003，错误详情显示具体原因 |
| 网络超时（60s） | 返回 40004，前端显示"生成超时" + 重试按钮 |
| 模型返回空内容 | 自动重试 1 次（更严格的提示词），仍空则提示用户 |
| 生成过程中断网 | 前端保留已接收的增量内容，不丢失 |

---

## 10. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC27 | AI 配置创建/更新/删除 | 自动化：PUT → GET → 数据一致 → DELETE → 404 |
| AC28 | API Key 加密存储 | 自动化：PUT → 检查数据库 api_key_encrypted 为密文 |
| AC29 | 测试连接成功 | 自动化：POST /test 有效 Key → ok: true |
| AC30 | 测试连接失败 | 自动化：POST /test 无效 Key → ok: false + error |
| AC31 | 无 AI 配置时生成返回 40001 | 自动化：DELETE 配置 → POST generate → 40001 |
| AC32 | 单章节流式生成 | E2E：点击"AI 生成" → 编辑器实时显示增量内容 |
| AC33 | 生成内容保存 | E2E：生成完成 → 刷新 → 重新打开章节 → 内容保留 |
| AC34 | 批量生成进度推送 | E2E：批量生成 → 前端显示 "3/15" 进度 |
| AC35 | 不支持的章节拒绝生成 | 自动化：对 ai_generatable=false 的章节 POST generate → 40002 |
| AC36 | 停止生成 | E2E：生成中点击停止 → 内容停止更新 |
| AC37 | 错误时保留已接收内容 | E2E：生成中模拟断网 → 编辑器保留已生成的文本 |
