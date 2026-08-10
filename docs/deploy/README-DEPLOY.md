# 数字化应急预案生成系统 部署手册

> 适用：公司网关 nginx 子路径部署（参考服务器 `deom2025.sxbych.com`）。
> 原则：**改部署路径只改构建参数，不改代码**。发现需要改代码才能部署的问题，请把改动回灌仓库。

## 1. 部署拓扑

```text
浏览器
  │
  ▼
网关 nginx（proxy 容器，宿主机端口 15000）
  ├── /emergency-plan-migration/  → 静态 dist（alias 容器内路径）
  ├── /api/                       → 反代宿主机 backend 容器 :8000
  └── /uploads/                   → 反代宿主机 backend 容器 :8000
                                        │
                                        ▼
                              backend（uvicorn :8000）+ postgres:16（Debian）
```

## 2. 部署前环境预检表

| 项 | 需要确认 | 说明 |
| --- | --- | --- |
| 服务器 OS | CentOS 7 及更老？ | glibc 2.17 无法直接运行 Node 18+ 官方二进制，必须用 node:20 容器构建 |
| Docker | 版本、卷挂载是否正常 | CentOS 7 XFS+overlay2 下 postgres 必须用 Debian 版镜像（非 alpine） |
| 域名 | 例如 deom2025.sxbych.com | 网关 server_name / 证书 |
| 子路径 | 例如 /emergency-plan-migration/ | 构建参数 `VITE_BASE_PATH` 必须与网关 location 一致 |
| 宿主机 IP | backend 容器所在宿主机 IP | 网关容器内 proxy_pass 不能用 127.0.0.1 |
| 端口 | backend 8000、网关 15000 | 防火墙放行 |
| 静态目录 | 网关挂载的 html 目录 | 权限需让 nginx worker 可进入（`chmod o+x` 父目录链） |
| 镜像源 | 外网可达性 | npm 用 registry.npmmirror.com；pip 已内置清华源 |
| 数据 | 全新库还是已有数据 | 全新库走 db-init 自动恢复；已有库跳过 db-init 并手动迁移 |
| ENCRYPTION_KEY | 与数据来源一致 | 改了就解不开数据库里的 AI Key |
| SECRET_KEY | 生产化 | 建议随机长字符串；改动后所有登录态失效 |

## 3. 前端构建

CentOS 7 无法直接跑 Node 官方二进制，统一用 node:20 容器构建（react-router-dom@7.17 要求 Node >= 20）：

```bash
docker run --rm -v $PWD/frontend:/app -w /app \
  -e VITE_BASE_PATH=/emergency-plan-migration/ \
  node:20 sh -c "npm config set registry https://registry.npmmirror.com && npm ci && npm run build"
```

产物在 `frontend/dist/`。npm 报 ECONNRESET 时先确认 registry 已切到 npmmirror。

## 4. 后端部署

```bash
cp .env.example .env          # 按预检表修改 SECRET_KEY / POSTGRES_PASSWORD 等
docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d --build
```

- 注意：`--project-directory .` 必须带，否则 compose 的相对路径会按 `deploy/` 目录解析，构建必然失败。
- 全新库：首次启动 postgres 自动执行 `db-init/` 下 SQL（01_restore.sql 为全量恢复）。
- 已有库：**不要**挂 db-init 目录（或确保文件名不与已有执行冲突），增量迁移 SQL 需手动应用。
- 首次启动后确认 chroma ONNX 模型缓存：`model-cache/chroma/onnx_models/all-MiniLM-L6-v2/` 需存在，
  否则首次向量化会尝试从外网下载（海外 S3 极慢）。从现有部署复制：
  `docker cp <旧backend容器>:/root/.cache/chroma/. model-cache/chroma/` 或直接拷贝模型目录。

## 5. 静态文件发布

```bash
mkdir -p <网关静态目录>/emergency-plan-migration
cp -r frontend/dist/* <网关静态目录>/emergency-plan-migration/
chmod o+x <网关静态目录> <网关静态目录>/emergency-plan-migration   # 父目录链都要可进入
```

## 6. 网关 nginx 配置

参照 `deploy/gateway-nginx.conf.example` 修改网关 `root_domain.conf`：

```bash
# 若从 Windows 复制过配置文件，先去掉 BOM：
sed -i '1s/^\xEF\xBB\xBF//' /home/sxby/nginx/conf/root_domain.conf
docker restart proxy
```

三条铁律：文件无 BOM；`alias` 写容器内路径；`proxy_pass` 写宿主机 IP（不用 127.0.0.1）。

## 7. 部署验证

```bash
./scripts/deploy-check.sh https://deom2025.sxbych.com/emergency-plan-migration/ https://deom2025.sxbych.com
```

全部 PASS 才算部署完成。浏览器冒烟清单：

- [ ] 桌面端：https://域名/子路径/ 登录成功，侧边菜单高亮正常
- [ ] 移动端：/子路径/m/dashboard 打开，底部 Tab 正常
- [ ] 生成预案 / 导出 / 上传图片 无 404
- [ ] PWA 可安装（manifest 正常）

## 8. 踩坑记录

| # | 坑 | 原因 | 解决 |
| --- | --- | --- | --- |
| 1 | postgres:16-alpine 启动失败 | CentOS 7 XFS+overlay2 卷挂载 initdb 写 postmaster.pid 报 Operation not permitted | 改用 postgres:16（Debian 版） |
| 2 | nginx 启动 unknown directive server | Windows 编辑的配置带 UTF-8 BOM | `sed -i '1s/^\xEF\xBB\xBF//' 文件` |
| 3 | 静态资源 404 | 父目录权限 750，nginx worker 进不去 | `chmod o+x` 父目录链 |
| 4 | 500 rewrite 重定向循环 | alias 写了宿主机路径 | alias 必须写容器内路径 |
| 5 | 构建报 EBADENGINE | react-router-dom@7.17 要求 Node >= 20，node:18 不行 | 用 node:20 容器构建 |
| 6 | npm install ECONNRESET | 外网 npm 不稳 | 切 registry.npmmirror.com |
| 7 | 网关反代 502 | proxy_pass 用 127.0.0.1 指向容器自身 | 用宿主机 IP |

## 9. 回滚

```bash
# 前端/配置：先备份再替换
cp -r <网关静态目录>/emergency-plan-migration ~/backups/emergency-plan-migration-dist-$(date +%Y%m%d)
cp /home/sxby/nginx/conf/root_domain.conf ~/backups/root_domain.conf.$(date +%Y%m%d)

# 数据库
./scripts/backup.sh    # pg_dump 到 backups/

# 旧版本包回退：解压旧 tar.gz，重新执行 4-6 节
```

## 10. 常见问题

- 页面白屏/资源 404 → 检查 `VITE_BASE_PATH` 与网关 location 是否一致，dist 是否复制到正确子目录
- 登录后跳转 404 → 检查路由 basename（代码已支持，无需改）
- 上传/接口 502 → 检查网关 proxy_pass 的宿主机 IP 与 backend 端口
- 首次生成预案卡住 → 检查 chroma ONNX 模型缓存是否存在（见第 4 节）
