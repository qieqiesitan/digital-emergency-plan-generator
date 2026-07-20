# 代码库优化方案

> 生成日期：2026-07-20
> 基于全代码库系统性审查结果编制

---

## 目录

1. [架构层重构（P0）](#1-架构层重构p0)
2. [模块级重构（P1）](#2-模块级重构p1)
3. [文件级清理（P1-P2）](#3-文件级清理p1-p2)
4. [实施路线图](#4-实施路线图)
5. [验证策略](#5-验证策略)

---

## 1. 架构层重构（P0）

### 1.1 统一 LLM 调用层

**现状**：5 套 LLM 调用函数分布在 chat.py 和 generation.py 中，各自维护独立逻辑。

**目标**：创建 services/llm_client.py，对外暴露 `llm_call(messages, ai_config, stream)` 和 `llm_call_structured()` 两个统一入口。

**实施**：
1. 创建 services/llm_client.py，合并 `_decrypt_api_key`、base URL 映射、payload 构建
2. 逐一替换 5 个调用方
3. 删除被替换的函数

### 1.2 合并 generation.py 批量生成逻辑

**现状**：`generate_batch` 和 `generate_batch_background` 共享 ~80% 代码。

**目标**：抽取 `run_batch_generation` 公共引擎，通过 callback 区分流式和静默模式。

### 1.3 泛化 chat_dispatch.py CRUD 模式

**现状**：30+ 处理函数手写相同 CRUD 模板。

**目标**：引入 `EntityConfig` 声明式注册 + `_generic_*` 泛化处理器，保留非 CRUD 函数手动实现。

### 1.4 合并 Mermaid 渲染管道

**现状**：8 个函数/3 个文件处理同一流程。

**目标**：合并到 services/mermaid_renderer.py，暴露 4 个公共函数。

---

## 2. 模块级重构（P1）

### 2.1 消除延迟导入

将 chat_dispatch.py、chat.py、prompt_cache.py 中的函数内 import 移至模块顶部。 
重构 `dependencies.py ↔ main.py` 的循环依赖。

### 2.2 RiskAssessment / ResourceInvestigation 模型合并

创建 `BaseReport` 抽象基类，共享字段。 Schema 层也使用泛化 Response。

### 2.3 Enterprise Schema 字段重复消除

创建 `EnterpriseBase(BaseModel)`，Create/Update/Response 通过继承消除 30+ 字段重复定义。

### 2.4 企业数据收集函数合并

`_collect_enterprise_data`（generation.py）和 `build_risk_assessment_context`（risk_assessment_service.py）合并为 `services/enterprise_data_provider.py`。

---

## 3. 文件级清理（P1-P2）

### 3.1 清理 backend/scripts/ 历史脚本
保留：build_regulation_index.py、migrate_to_article_level.py
归档其余 17 个历史修复脚本到 scripts/archive/

### 3.2 清理根目录脚本
移走 6 个测试/修复脚本和 -w 文件

### 3.3 清理冗余 venv（backend/venv）

### 3.4 处理前端空壳组件
删除或补全 12 个 0-3 行的空组件文件

### 3.5 统一 _sse 辅助函数
创建 services/sse_utils.py，统一两种 SSE 格式

---

## 4. 实施路线图

```
Phase 1（P0 · 2-3 天）
├── 1.1 统一 LLM 调用层
├── 1.3 泛化 chat_dispatch CRUD
├── 3.1 清理 backend/scripts/
├── 3.2 清理根目录脚本
└── 3.5 统一 _sse 辅助函数

Phase 2（P0 · 2 天）
├── 1.2 合并 generation.py 批量生成
├── 1.4 合并 Mermaid 渲染管道
└── 2.1 消除延迟导入

Phase 3（P1 · 2-3 天）
├── 2.2 RiskAssessment/ResourceInvestigation 合并
├── 2.3 Enterprise Schema 字段消除
├── 2.4 企业数据收集合并
└── 3.3 清理冗余 venv

Phase 4（P1-P2 · 1 天）
├── 3.4 前端空壳组件处理
├── docx_template.py 样式配置化
└── 验证阶段
```

## 5. 验证策略

| 重构项 | 验证方式 |
|---|---|
| LLM 调用统一 | 3 种厂商流式/非流式请求，输出一致 |
| CRUD 泛化 | 32 个函数调用输入输出一致 |
| generation 合并 | 批量生成 SSE 事件序列 + DB 状态一致 |
| Mermaid 合并 | 3 个版本对同一 Markdown 输出一致 |
| Schema 合并 | Pydantic fields 集合与字典序一致 |
| 空壳组件 | npm run build 无 missing module 错误 |
