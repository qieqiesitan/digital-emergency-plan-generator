---
name: iconfont-selector
description: 当设计或前端任务需要从阿里 iconfont.cn 自选图标或插画时使用——替换 AntD 图标、设计稿配图、安全标志 SVG、页面空态插画、字体图标。触发场景：需要搜索、挑选、下载 iconfont 图标 / SVG 图标 / 矢量插画。
---

# iconfont 图标自选

## 概述

通过 iconfont.cn 公开搜索接口（免登录、免 API key）搜索并下载 SVG 图标/插画，供设计稿与前端界面使用。

## 工作流

1. **搜索**：运行 `python .codex/skills/iconfont-selector/scripts/search_iconfont.py "关键词" --limit 20`
   - 中文关键词效果最好（如「消防」「危化品」「组织架构」「风险」）
   - 插画用 `--type illustration`；按线条/面性用 `--fills line|fill`；按热门度 `--sort popular`
2. **挑选**：根据返回的名称 / id / font_class 选择最贴合的图标；可多关键词多轮搜索对比，再向用户展示候选清单
3. **落盘**：加 `--out-dir <目录>` 下载 SVG 文件；设计稿可直接内联返回的 `svg` 字段内容，无需下载
4. **版权确认**：商用项目优先选图标详情页标注「免费商用」的图标；禁止将图标转售、禁止用于模型训练；官方库商用需书面授权
5. **生产集成**：SVG 存本地，不依赖 iconfont CDN（阿里声明 CDN 仅供体验调试、不承诺稳定）
   - 本项目惯例：安全标志在 `backend/app/static/signs`，UI 图标放 `frontend/src/assets`

## 常见错误

- 接口偶发 5xx 或限流：等几秒重试；仍失败则降级为 AntD 图标，或请用户提供 iconfont 项目/公开集合链接
- 插画 SVG 有防盗链：脚本已自动带 Referer 头，无需手动处理
- 文件名含特殊字符：脚本自动清洗为安全文件名

## 需要用户配合的场景

- 用户已有 iconfont「我的项目」：请其分享项目或公开集合链接，按项目提取图标
- 需要整包字体图标（font-class / unicode / symbol）：请用户发布项目并给 CDN 链接，拿到后下载字体与 CSS/JS 到本地

## 资源

- `scripts/search_iconfont.py`：搜索 + 下载脚本（Python 标准库，`python --help` 查看全部参数）
