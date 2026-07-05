# 预案系统接入 PROTEGO 商城 —— 对接文档

> 状态：预案生成系统侧已完成，PROTEGO 侧待实施  
> 更新：2026-07-04

---

## 一、架构

```
PROTEGO 商城 (Spring Boot :8081)
  │
  ├─ ReportGatewayService.pushToExternal()
  │     HMAC签名 → POST http://emergency-plan-backend:8000/api/external/plans
  │
  ├─ CallbackController  ←──  预案系统回调
  │     POST /api/v1/callbacks/report-status  (HMAC验签)
  │
  └─ 轮询 GET /api/reports/by-order/{orderId}

                    ↕ ywt-net (Docker)

预案生成系统 (FastAPI :8000)
  │
  ├─ /api/external/plans        POST   创建预案 → AI生成 → DOCX导出 → 回调
  ├─ /api/external/plans/{id}/status   GET    查询进度
  └─ /api/external/plans/{id}/files/{id}  GET  下载DOCX
```

两边通过 Docker 网络 `ywt-net` 互通，容器名直连，不暴露公网端口。

---

## 二、共享密钥（两边完全一致）

```
HMAC_SECRET = "protego-emergency-plan-hmac-secret-2026!!"
```

**校验方式**：HMAC-SHA256，签名内容为 `{METHOD}\n{PATH}\n{TIMESTAMP}\n{BODY}`。

---

## 三、预案生成系统侧（已完成✅）

### 3.1 docker-compose.yml 环境变量

在 `emergency-plan-backend` 容器追加以下两行：

```yaml
  backend:
    environment:
      # ... 原有配置 ...
      EXTERNAL_API_HMAC_SECRET: "protego-emergency-plan-hmac-secret-2026!!"
      PROTEGO_CALLBACK_URL: "http://protego-server:8081/api/v1/callbacks/report-status"
```

完整 backend 环境变量：

```yaml
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: emergency-plan-backend
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/emergency_plan
      SECRET_KEY: emergency-plan-docker-secret-key-2026
      ACCESS_TOKEN_EXPIRE_MINUTES: "30"
      REFRESH_TOKEN_EXPIRE_DAYS: "7"
      ENCRYPTION_KEY: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
      EXPORT_DIR: /app/exports
      YWT_GATEWAY_URL: http://ywt-gateway:8080
      YWT_API_KEY: 893e5e15d3b444dbbebb1dac44b720f2
      YWT_SYS_CODE: emergency-plan
      YWT_JWT_SECRET: yewuzhongtai-jwt-secret-key-2024-min-256-bits!!
      # ⬇ 新增
      EXTERNAL_API_HMAC_SECRET: "protego-emergency-plan-hmac-secret-2026!!"
      PROTEGO_CALLBACK_URL: "http://protego-server:8081/api/v1/callbacks/report-status"
```

> 如果回调 URL 不需要（或 PROTEGO 侧暂未实现回调端点），`PROTEGO_CALLBACK_URL` 可留空，预案系统会跳过回调步骤但仍正常生成 DOCX。

### 3.2 新增/修改文件清单

| 文件 | 说明 |
|------|------|
| `backend/app/config.py` | 新增 `EXTERNAL_API_HMAC_SECRET`, `PROTEGO_CALLBACK_URL` |
| `backend/app/middleware/hmac_auth.py` | **新建** HMAC 签名验证中间件（时钟偏差 ±5min） |
| `backend/app/services/external_file_store.py` | **新建** 外部 URL 文件下载到本地 |
| `backend/app/services/external_service.py` | **新建** 回调 HTTP 客户端（HMAC 签名 + 3次重试） |
| `backend/app/routers/external.py` | **新建** 3 个对外端点 |
| `backend/app/main.py` | 注册 HmacAuthMiddleware + external 路由器 |

---

## 四、PROTEGO 商城侧（待实施）

### 4.1 docker-compose.yml 环境变量

在 `protego-server` 容器追加：

```yaml
  protego-server:
    environment:
      # ... 原有配置 ...
      REPORT_SYSTEM_BASE_URL: "http://emergency-plan-backend:8000"
      REPORT_HMAC_SECRET: "protego-emergency-plan-hmac-secret-2026!!"
```

完整 protego-server 环境变量：

```yaml
  protego-server:
    build:
      context: ./apps/server
      dockerfile: Dockerfile
    container_name: protego-server
    environment:
      SPRING_DATASOURCE_URL: jdbc:postgresql://protego-db:5432/protego
      SPRING_DATASOURCE_USERNAME: protego
      SPRING_DATASOURCE_PASSWORD: protego123
      YWT_GATEWAY_URL: http://ywt-gateway:8080
      # ⬇ 新增
      REPORT_SYSTEM_BASE_URL: "http://emergency-plan-backend:8000"
      REPORT_HMAC_SECRET: "protego-emergency-plan-hmac-secret-2026!!"
```

### 4.2 application.yml 新增配置

```yaml
report-system:
  base-url: ${REPORT_SYSTEM_BASE_URL:http://emergency-plan-backend:8000}
  shared-secret: ${REPORT_HMAC_SECRET:protego-emergency-plan-hmac-secret-2026!!}
  callback-host: http://protego-server:8081
```

### 4.3 需新建/修改的文件

| 文件 | 动作 | 说明 |
|------|------|------|
| `util/HmacUtils.java` | 新建 | HMAC-SHA256 签名/验签工具类 |
| `service/ReportGatewayService.java` | 重写 | pushToExternal() → 真实 HTTP 调用 |
| `controller/CallbackController.java` | 新建 | `POST /api/v1/callbacks/report-status` 回调入口 |
| `service/ReportCallbackService.java` | 新建 | 验签 → 更新 report_requests → 更新 order 状态 |
| `service/OrderService.java` | 扩展 | 支付确认成功后自动调用 pushToExternal |
| `model/Product.java` | 扩展 | 新增 `planType` 字段（VARCHAR） |
| `model/ReportRequest.java` | 扩展 | 新增 `externalTaskId`(VARCHAR), `progress`(INT) |
| `resources/application.yml` | 修改 | 新增 report-system 配置块 |

---

## 五、API 接口规范

### 5.1 POST /api/external/plans — 创建预案

**请求头（必填）**：

```
Content-Type: application/json
X-Signature: <HMAC-SHA256 签名>
X-Timestamp: <Unix 秒级时间戳>
```

**请求体**：

```json
{
  "external_order_id": "PROTEGO-order-123",
  "external_user_id": "user-456",
  "plan_type": "comprehensive",
  "enterprise": {
    "name": "西安喜来登大酒店",
    "industry": "酒店",
    "contact_name": "张三",
    "contact_phone": "13800138000"
  },
  "documents": [
    {
      "name": "企业营业执照.pdf",
      "url": "https://protego-oss.example.com/files/license.pdf",
      "type": "license"
    }
  ],
  "callback_url": "http://protego-server:8081/api/v1/callbacks/report-status"
}
```

**plan_type 取值**：

| 值 | 含义 |
|----|------|
| `comprehensive` | 综合应急预案 |
| `special` | 专项应急预案 |
| `on_site` / `onsite` | 现场处置方案 |
| `all` | 全套应急预案 |

**成功响应 (200)**：

```json
{
  "code": 0,
  "data": {
    "task_id": "a1b2c3d4-...",
    "status": "accepted",
    "estimated_minutes": 15
  }
}
```

### 5.2 GET /api/external/plans/{task_id}/status — 查询进度

**请求头**：同 5.1（HMAC 签名）

**成功响应**：

```json
{
  "code": 0,
  "data": {
    "task_id": "a1b2c3d4-...",
    "status": "generating",
    "progress": 45,
    "files": []
  }
}
```

**status 取值**：`generating` → `completed` / `failed`

### 5.3 GET /api/external/plans/{task_id}/files/{file_id} — 下载文件

**请求头**：同 5.1（HMAC 签名）

**响应**：`Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document` 二进制流。

---

## 六、回调规范（预案系统 → PROTEGO）

### 6.1 回调请求

预案系统在 AI 生成 + DOCX 导出完成后，向创建时传入的 `callback_url` 发 POST：

**请求头**：

```
Content-Type: application/json
X-Signature: <HMAC-SHA256 签名>
X-Timestamp: <Unix 秒级时间戳>
```

**请求体**：

```json
{
  "task_id": "a1b2c3d4-...",
  "external_order_id": "PROTEGO-order-123",
  "status": "completed",
  "files": [
    {
      "name": "西安喜来登大酒店-综合应急预案.docx",
      "url": "/api/external/plans/a1b2c3d4-.../files/a1b2c3d4-...",
      "size": 245760
    }
  ]
}
```

**status 取值**：`completed` / `failed`

### 6.2 回调重试策略

- 最多重试 **3 次**
- 间隔递增：2s → 4s → 6s
- 3 次均失败则放弃，记录日志

---

## 七、HMAC 签名算法

### 签名构造

```
待签名字符串 = HTTP方法 + "\n" + 请求路径 + "\n" + 时间戳 + "\n" + 请求体
签名 = HMAC-SHA256(共享密钥, 待签名字符串) → 十六进制小写
```

### 示例

```
方法:     POST
路径:     /api/external/plans
时间戳:   1750089600
请求体:   {"external_order_id":"..."}

待签名:   POST\n/api/external/plans\n1750089600\n{"external_order_id":"..."}
签名:     a3f8c2d1...
```

### 验证要点

1. 时间戳与服务器时间相差不超过 **300 秒（5 分钟）**
2. 使用 `hmac.compare_digest` 做恒定时间比较防时序攻击
3. 请求体为空时，待签名字符串中 body 部分为空字符串

---

## 八、数据映射速查

| PROTEGO 字段 | 预案系统字段 | 转换逻辑 |
|-------------|------------|---------|
| `Order.id` | `external_order_id` | 透传 |
| `Order.userId` | `external_user_id` → `User.ywt_user_id` | 按 ID 查找，不存在自动创建 |
| `Order.enterpriseName` | `Enterprise.name` | 按名称 + user_id 去重，不存在自动创建 |
| `Order.contactName/Phone` | `Enterprise` 联系人 | 自动填充 |
| `Product.planType` | `plan_type` | 透传 |

---

## 九、启动顺序与验证

### 启动顺序

```
1. docker-compose up -d postgres protego-db    # 数据库
2. docker-compose up -d emergency-plan-backend  # 预案系统
3. docker-compose up -d protego-server          # PROTEGO
```

### 验证 HMAC 连通性

```bash
# 在 PROTEGO 容器内测试
TIMESTAMP=$(date +%s)
BODY='{"external_order_id":"test-001","external_user_id":"test-user","plan_type":"comprehensive","enterprise":{"name":"测试企业","industry":"测试"},"documents":[],"callback_url":""}'
SIGNATURE=$(echo -n "POST\n/api/external/plans\n${TIMESTAMP}\n${BODY}" | openssl dgst -sha256 -hmac "protego-emergency-plan-hmac-secret-2026!!" | awk '{print $2}')

curl -X POST http://emergency-plan-backend:8000/api/external/plans \
  -H "Content-Type: application/json" \
  -H "X-Timestamp: ${TIMESTAMP}" \
  -H "X-Signature: ${SIGNATURE}" \
  -d "${BODY}"
```

预期响应：`{"code":0,"data":{"task_id":"...","status":"accepted","estimated_minutes":15}}`

---

## 十、异常处理

| 场景 | 预案系统行为 | PROTEGO 处理建议 |
|------|------------|----------------|
| HMAC 签名错误 | 返回 401 | 检查共享密钥是否一致、时钟是否同步 |
| 时间戳过期 | 返回 401 | 确保服务器时间同步（NTP） |
| 外部用户无 AI 配置 | 返回 `failed` | 预案系统管理员需提前为外部用户配置 AI Key |
| 预案系统不可达 | — | 重试 3 次，记录 `report_api_logs`，订单保持 `report_pending` |
| 回调失败（3次） | 放弃，记录日志 | 主动轮询 `GET /api/reports/by-order/{orderId}` 获取最终状态 |
| 重复回调 | 正常处理 | 回调处理逻辑需幂等（检查 task_id 是否已处理） |

---

> **PROTEGO 侧实施时**，重点参考本项目的 `backend/app/middleware/hmac_auth.py`（签名逻辑）和 `backend/app/services/external_service.py`（回调逻辑），用 Java 实现同等功能即可。
