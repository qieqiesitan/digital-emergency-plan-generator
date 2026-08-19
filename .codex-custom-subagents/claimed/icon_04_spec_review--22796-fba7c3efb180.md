# Codex Custom Subagents task handoff v1

Task: icon_04_spec_review

## 目标

审查任务 4（主导航业务菜单图标替换）实现是否与规格匹配——**不多不少**。独立阅读实际代码验证，不要信任实现者报告。

## 审查对象

工作区：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\icon-system`（分支 codex/icon-system）
实现提交：`31a5618`（父提交 `85296ad`）「feat(icon-system): replace main menu business icons with AppIcon」
前端命令在 `frontend/` 目录下运行。

## 要求的内容（规格）

1. 修改 `frontend/src/layouts/MainLayout.tsx`：
   - 顶部新增 `import AppIcon from "@/components/common/AppIcon";`；
   - 7 个业务菜单项 icon 替换为 `<AppIcon name="..." size={14} />`：工作台→dashboard、企业管理→enterprise、预案列表→plan-list、法规库管理→regulations、数据字典管理→data-dict、提示词管理→prompt、AI 配置→ai；
   - 替换后清理不再使用的 AntD import（以 eslint unused 为准）；
   - **保留不动**：用户管理（TeamOutlined）、角色管理（SafetyCertificateOutlined）、系统配置（SettingOutlined）、个人资料（UserOutlined）、退出登录（LogoutOutlined），以及头像下拉菜单同名入口。
2. 门禁：`npx tsc -b` exit 0；`npx eslint src/layouts/MainLayout.tsx` exit 0；`npx vitest run` 130 passed。
3. 提交契约：恰含 MainLayout.tsx 一个文件；消息精确；`git show --check` 干净。

## 实现者声称构建了什么

（供参考，须独立验证）实现者报告：7 项替换完成、import 清理（保留 KeyOutlined 因头像下拉仍用）、门禁全绿、截图确认 14px 无错位、提交 31a5618 恰 1 文件。

## 审查方法

1. `git -C <worktree> show --stat 31a5618` 核对范围与消息；
2. 通读 MainLayout.tsx 菜单相关代码：7 个替换点 name 精确、size=14；5 个保留项仍是 AntD；头像下拉未动；
3. 核对 import 清理正确（无残留 unused，也未误删仍使用的图标）；
4. 独立运行：`npx tsc -b`、`npx eslint src/layouts/MainLayout.tsx`、`npx vitest run`（frontend/ 下）；
5. 检查有无规格外改动。

## 汇报格式

- ✅ 符合规格（代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失/多余/偏差，附带 file:line 或命令证据]

## 认领方式（必须先做）

在目录 `C:\Users\55061\Documents\数字化预案自动生成 2` 下运行：

```
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace . --agent deepseek_anthropic_worker --model deepseek-v4-flash --provider deepseek_anthropic
```

无子命令即原子认领一个 pending 任务，返回 JSON 含 `path`；**先读该文件**再开始。认领 status 非成功立即上报。

## 约束

- 只读审查，不得修改任何文件；不得信任实现者报告。
