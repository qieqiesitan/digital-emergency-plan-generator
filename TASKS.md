# 当前任务追踪

> 每次对话有进展后更新此文件。

## 🔴 当前状态快照（压缩恢复用）
- 正在做什么：风险评估+应急资源调查提示词配置化全部完成
- 刚完成的动作：
  1. SQL迁移：13条报告提示词模板写入中台DB（RA 6条 + RI 7条）
  2. prompt_cache.py：扩大加载范围（所有category）+ 新增 get_report_system_prompt / get_report_section_prompt
  3. risk_assessment_service.py：build_chapter_prompt 接入模板 + _get_ra_system_prompt
  4. resource_investigation_service.py：同上
  5. risk_assessment.py / resource_investigation.py 路由：SYSTEM_PROMPT 改为动态获取
  6. 前端 PromptManagePage：5个Tab（综合/专项/现场/风险评估/资源调查）+ 章节映射
  7. Git 备份 + 后端重启
- 下一步动作：用户在提示词管理页面验证5个Tab，测试生成风险评估/资源调查报告
- 关键上下文：
  - 模板总数：64条（system 6 + emergency_section 44 + RA/RI 11 + mermaid 1 + surrounding 2）
  - 加载时间：首次约30秒，缓存TTL 5分钟
  - 旧报告系统提示词保留为硬编码兜底，DB模板优先

## 进行中的任务

## 已完成
- ✅ 提示词模板三层细化（应急预案）
- ✅ 风险评估+应急资源调查提示词配置化
- ✅ 菜单路径根因分析 + 修复
- ✅ qiankun 白屏修复
- ✅ graphify 增量更新

## 阻塞点

## 环境速查
- 项目路径：C:\Users\55061\Documents\数字化预案自动生成 2
- 后端：http://localhost:8000 ⚡运行中
- 前端：http://localhost:5173 ⚡运行中
- 中台：http://localhost:80 / http://localhost:8088 ⚡运行中
- 中台DB：localhost:5432 / yewuzhongtai
- 预案DB：localhost:5438 / emergency_plan
