# 构建一致性检查清单

每次新项目初始化、接手已有项目、或执行构建前，自动执行此清单。

---

## 1. 锁文件完整性
- [ ] `package-lock.json` / `yarn.lock` / `pnpm-lock.yaml` 存在且被 git 跟踪
- [ ] 若不存在 → 运行包管理器 install 生成，并立即提交
- [ ] 若 `package.json` 手动修改了版本号但锁文件未更新 → 提醒用户先跑 install 更新锁文件

## 2. 安装命令一致性
- [ ] Dockerfile / CI 配置中安装命令是 `npm ci`（非 `npm install`）
- [ ] 如果是 `npm install` → 改为 `npm ci`，或 `npm ci 2>/dev/null || npm install` 兜底
- [ ] 加新依赖时用 `npm install <pkg>`，日常开发统一用 `npm ci`

## 3. build 脚本检查
- [ ] `package.json` 的 `scripts.build` 同时包含类型检查和实际构建
- [ ] 如果类型检查有**大量历史遗留**错误阻塞构建 → 先放宽 tsconfig lint 级选项（`noUnusedLocals: false`、`noUnusedParameters: false`），保留语法级错误检测
- [ ] 如果只是个别文件的 syntax error 或类型不匹配 → 直接修复，不跳过检查

## 4. `.dockerignore` 防护
- [ ] `.dockerignore` 存在，至少包含：
  ```
  node_modules
  dist
  .git
  ```
- [ ] 防止本地残留的旧 `node_modules` 或构建产物被 `COPY . .` 带入 Docker 镜像

## 5. 本地干净环境验证
- [ ] 执行 `rm -rf node_modules && npm ci && npm run build`
- [ ] 失败 → 在此修复，不推到远端
- [ ] 成功 → 记录 Node 版本和关键依赖版本

## 6. 依赖版本锁定策略
- [ ] 关键依赖（TypeScript、Vite、框架）使用 `~` 或精确版本，避免 `^` 大版本跳跃
- [ ] 每月执行一次 `rm -rf node_modules && npm ci && npm run build` 周期验证
