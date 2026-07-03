# 提示词系统备份

## 文件说明

| 文件 | 用途 |
|------|------|
| seed_prompts_full.py | 60条提示词模板种子脚本（自包含，含完整模板正文） |
| seed_prompts_full.json | 同上（JSON格式，供参考） |
| prompt.py | PromptTemplate 数据库模型 |
| prompt_cache.py | 双模缓存（YWT在线同步 + 本地DB兜底 + 本地修改保护） |
| prompts.py | 提示词管理CRUD路由 |
| generation.py | 预案生成核心（accident_type贯穿 + 前文上下文 + 第一章增强） |
| docker-compose.yml | 含前端/后端源码 volume 挂载（即时生效） |

## 新环境部署步骤

1. 将 backup/ 下所有 .py 文件覆盖到对应位置：
   - prompt.py → backend/app/models/
   - prompt_cache.py → backend/app/services/
   - prompts.py → backend/app/routers/
   - generation.py → backend/app/routers/
   - seed_prompts_full.py → backend/
   - docker-compose.yml → 项目根目录（或用其中的 volume 挂载配置）

2. 启动服务
   docker compose up -d

3. 导入提示词模板（幂等，可重复执行）
   docker exec emergency-plan-backend python seed_prompts_full.py

4. 重启后端生效
   docker restart emergency-plan-backend

## 模板内容概要

- 综合应急预案：25个章节模板（含 {{first_chapter_hint}}、变量说明脚注）
- 专项应急预案：9个章节模板（含 {{accident_type}} 事故类型行、变量说明脚注）
- 现场处置方案：5个章节模板（含 {{accident_type}} 事故类型行、变量说明脚注）
- 系统提示词：4个（综合/专项/现场/默认）
- 流程图提示词：1个
- 风险评估报告：7个模板
- 应急资源调查报告：7个模板
- 周边环境：2个模板

## 运行时特性

- 前文章节全文自动注入（previous_context，模板无需显式引用）
- 第一章自动提示参考报告全文（first_chapter_hint）
- accident_type 独立模板变量，专项/现场方案自动渲染为事故类型
- YWT在线时仅同步新模板，不覆盖本地修改
- YWT离线时本地DB独立运行
