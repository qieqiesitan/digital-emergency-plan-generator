# 技术债清理实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 清理部署可交付性增强（e4ff517）收尾时记录的 7 项技术债，恢复确定性安装、修复边界缺陷、移除敏感文件、补齐配置说明。

**架构：** 全部为小范围配置/代码修正，不引入新依赖、不改后端业务逻辑；仅一处前端工具函数行为修正（stripAppBase 边界）走 TDD。

**技术栈：** TypeScript / Vite / docker compose / bash / npm。

**执行环境：** worktree `.worktrees/tech-debt-cleanup`（分支 `codex/tech-debt-cleanup`，基于 master e4ff517）。前端命令在 `frontend/` 子目录执行。

**依据：** 任务 1-13 审查报告与 TASKS.md 技术债清单。

---

## 文件结构

| 文件 | 动作 | 内容 |
| --- | --- | --- |
| `frontend/src/utils/platform.ts` | 修改 | stripAppBase 前缀边界（等于 base 或 base+"/" 才剥离） |
| `frontend/src/utils/platform.test.ts` | 修改 | 补兄弟路径/精确 base 用例 |
| `frontend/vite.config.ts` | 修改 | VITE_BASE_PATH 前导斜杠校验 |
| `deploy/docker-compose.prod.yml` | 修改 | SECRET_KEY/POSTGRES_PASSWORD 改必填（:?）、补 PROTEGO 变量、postgres 防回退注释 |
| `.env.example` | 修改 | 补 EXTERNAL_API_HMAC_SECRET / PROTEGO_CALLBACK_URL |
| `frontend/nginx.conf` | 修改 | /api、/uploads 补「依赖 compose 网络」注释 |
| `scripts/archive/query_users.sql` | 删除 | 敏感 SQL（含 ALTER USER PASSWORD） |
| `scripts/archive/reset_pwd.sql` | 删除 | 敏感 SQL（含 bcrypt 哈希） |
| `frontend/package-lock.json` | 修改 | 与 package.json 同步（npm install 收敛） |
| `docs/deploy/README-DEPLOY.md` | 修改 | 后端部署节注明 .env 必填（SECRET_KEY/POSTGRES_PASSWORD 无默认） |

---

## 任务 1：stripAppBase 前缀边界修复（TDD）

**文件：** `frontend/src/utils/platform.ts`、`frontend/src/utils/platform.test.ts`

- [ ] **步骤 1：写失败测试**——在 `platform.test.ts` 追加：

```ts
  it("兄弟前缀路径不剥离", () => {
    expect(
      stripAppBase("/emergency-plan-migration2/m/login", "/emergency-plan-migration"),
    ).toBe("/emergency-plan-migration2/m/login");
  });

  it("pathname 恰等于 appBase 时剥离为空串", () => {
    expect(stripAppBase("/emergency-plan-migration", "/emergency-plan-migration")).toBe("");
  });
```

- [ ] **步骤 2：跑测试确认失败**（`npx vitest run src/utils/platform.test.ts`，兄弟路径用例 FAIL）
- [ ] **步骤 3：改实现**——`stripAppBase` 条件改为：

```ts
export function stripAppBase(pathname: string, appBase: string = APP_BASE): string {
  if (!appBase) return pathname;
  if (pathname === appBase || pathname.startsWith(`${appBase}/`)) {
    return pathname.slice(appBase.length);
  }
  return pathname;
}
```

- [ ] **步骤 4：跑测试确认全绿**（6 项）
- [ ] **步骤 5：Commit** `fix(deploy): bound stripAppBase prefix match to path segment`

## 任务 2：VITE_BASE_PATH 前导斜杠校验

**文件：** `frontend/vite.config.ts`

- [ ] **步骤 1：改实现**——在 `BASE_PATH` 常量之后追加：

```ts
if (process.env.VITE_BASE_PATH && !process.env.VITE_BASE_PATH.startsWith("/")) {
  throw new Error(
    `VITE_BASE_PATH 必须以 / 开头（当前: "${process.env.VITE_BASE_PATH}"），例如 /emergency-plan-migration/`,
  );
}
```

- [ ] **步骤 2：验证**——`$env:VITE_BASE_PATH="emergency-plan-migration/"; npx tsc -b` 后 `node -e "import('./vite.config.ts')"` 或 `npx vite build` 应立刻抛出该校验错误（在 Node24 构建崩溃之前触发，验证报错文案）；随后 `Remove-Item Env:VITE_BASE_PATH` 清理
- [ ] **步骤 3：Commit** `feat(deploy): validate VITE_BASE_PATH leading slash`

## 任务 3：生产 compose 密钥必填 + PROTEGO 变量 + 防回退注释

**文件：** `deploy/docker-compose.prod.yml`

- [ ] **步骤 1：改实现**：
  - `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}` → `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?必须在 .env 中设置 POSTGRES_PASSWORD}`；
  - `SECRET_KEY: ${SECRET_KEY:-emergency-plan-docker-secret-key-2026}` → `SECRET_KEY: ${SECRET_KEY:?必须在 .env 中设置 SECRET_KEY}`；
  - `DATABASE_URL` 同步去掉 `:-postgres` 默认，改用 `:?` 或引用 POSTGRES_PASSWORD（保持一处必填）；
  - backend environment 追加：
    ```yaml
      EXTERNAL_API_HMAC_SECRET: ${EXTERNAL_API_HMAC_SECRET:-}
      PROTEGO_CALLBACK_URL: ${PROTEGO_CALLBACK_URL:-}
    ```
  - postgres 服务加注释：`# 勿改回 postgres:16-alpine：CentOS 7 XFS+overlay2 卷挂载 initdb 报 Operation not permitted`。
- [ ] **步骤 2：验证**——`docker compose -f deploy/docker-compose.prod.yml --project-directory . --env-file .env.example config -q` 退出码 0；不带 `--env-file` 时应报「必须在 .env 中设置」错误（预期失败，验证必填生效）
- [ ] **步骤 3：Commit** `fix(deploy): require production secrets and expose PROTEGO env vars`

## 任务 4：.env.example 补 PROTEGO 变量

**文件：** `.env.example`

- [ ] **步骤 1：改实现**——在 QCC 块前追加：

```bash
# 外部系统接入（PROTEGO 商城，可选；留空则外部请求被拒绝并记录告警）
EXTERNAL_API_HMAC_SECRET=
PROTEGO_CALLBACK_URL=
```

- [ ] **步骤 2：验证**——`.env.example` 与 compose 变量名一致（rg 对照）
- [ ] **步骤 3：Commit** `chore(deploy): document PROTEGO env vars in template`

## 任务 5：nginx.conf 补 compose 网络注释

**文件：** `frontend/nginx.conf`

- [ ] **步骤 1：改实现**——在 `location /api/` 与 `location /uploads/` 的 `proxy_pass` 行前各加一行注释：`# 依赖 compose 网络解析 backend 主机名；独立容器运行需 --add-host backend:<IP> 或改用网关模板`
- [ ] **步骤 2：验证**——`docker run --rm -v ... nginx:alpine nginx -t`（含 `--add-host backend:127.0.0.1`）通过；`git diff --check` 干净
- [ ] **步骤 3：Commit** `docs(deploy): note compose network requirement for nginx upstream`

## 任务 6：删除 archive 敏感 SQL

**文件：** `scripts/archive/query_users.sql`、`scripts/archive/reset_pwd.sql`

- [ ] **步骤 1：删除**——`git rm scripts/archive/query_users.sql scripts/archive/reset_pwd.sql`
- [ ] **步骤 2：验证**——`rg -n "query_users|reset_pwd|ALTER USER" scripts/ deploy/ docs/deploy/` 无命中；`git show HEAD --stat` 确认删除
- [ ] **步骤 3：Commit** `chore(security): remove credential-bearing archive SQL from repo`

> 备注：git 历史仍保留旧内容；彻底清除需 filter-repo + 强制推送（另立任务，需用户确认）。

## 任务 7：package-lock 同步 + 全量门禁

**文件：** `frontend/package-lock.json`（可能含 `frontend/package.json`）

- [ ] **步骤 1：收敛 lock**——`cd frontend && npm install`（允许按需更新 lockfile），检查 `git diff --stat`，确认没有意外的大版本跳变（重点看 package.json 未被改）
- [ ] **步骤 2：干净安装验证**——`npm ci` 成功（lockfile 同步生效）
- [ ] **步骤 3：全量门禁**——`npx tsc -b` 0；`npx vitest run` 全绿；`git diff --check` 干净
- [ ] **步骤 4：Commit** `chore(frontend): sync package-lock with package.json`

---

## 收尾

- [ ] 全量门禁复验（tsc / vitest / bash -n 三个脚本 / `docker compose --env-file .env.example config -q`）
- [ ] 最终审查后按 finishing-a-development-branch 收尾（用户选合并方式）
