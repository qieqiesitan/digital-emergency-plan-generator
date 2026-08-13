# Codex Custom Subagents task handoff v1

Task: t06_review_quality2

## 任务：代码质量复审 —— 任务 6 修复（63dae2a）

你是一个代码质量审查子智能体。任务 6 原实现因「桌面深链回退 m.html」关键缺陷被打回，实现者已提交修复 63dae2a。本次复审确认修复有效且无新问题。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。复审范围：BASE `7abd9ee` → HEAD `63dae2a`，仅 `frontend/nginx.conf`（+18/-1）。

### 修复内容（对照任务给定文本）

```nginx
    # 无尾斜杠访问时 301 跳转
    location = /emergency-plan-migration {
        return 301 /emergency-plan-migration/;
    }

    # 应用子路径部署：dist 位于容器 html 根目录（alias 指向容器内路径，勿写宿主机路径）
    # 移动端路径优先匹配并回退 m.html；其余子路径回退桌面 index.html
    location /emergency-plan-migration/m/ {
        alias /usr/share/nginx/html/;
        try_files $uri $uri/ /emergency-plan-migration/m.html;
    }
    location /emergency-plan-migration/ {
        alias /usr/share/nginx/html/;
        try_files $uri $uri/ /emergency-plan-migration/index.html;
    }

    # 子路径静态资源长缓存（与根路径 /assets/ 对齐）
    location /emergency-plan-migration/assets/ {
        alias /usr/share/nginx/html/assets/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
```

### 复审要点

1. `git show 63dae2a` diff 与上述内容一致，提交只含 nginx.conf；
2. 容器实测（dist 需为子路径构建产物；如已存在 `frontend/dist` 子路径产物可直接挂载）：
   - 桌面首页与深链返回桌面 index.html（含「数字化预案系统」、不含「移动端」）；
   - 移动端深链返回 m.html（含「移动端」）；
   - 无尾斜杠 301；
   - `/emergency-plan-migration/assets/` 下真实资源返回 200 且带 immutable 缓存头（PWA 根目录 registerSW.js 无缓存头属构建产物差异，不算缺陷，可备注）；
3. 检查是否引入新问题（location 优先级、双回退链、与 /m/、/assets/、/api/、/uploads/ 的冲突）。

### 汇报格式

返回：✅ 通过 / ❌ 需修复（附实测证据与 file:line）。不要修改代码。
