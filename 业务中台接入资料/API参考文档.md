# 业务中台 API 参考文档

> 网关地址：`http://localhost:8088`（当前环境 GW_PORT=8088）
> 生成时间：2026-06-15

---

## 1. 自注册 API

子系统通过此组 API 自助接入业务中台，注册后获得 API Key 和网关路由。

---

### POST /api/registry/system — 系统自注册

子系统接入业务中台的唯一入口。注册成功后自动创建菜单、角色、管理员用户，并向 Nacos 追加网关路由。

**请求示例**

```bash
curl -X POST http://localhost:8088/api/registry/system \
  -H "Content-Type: application/json" \
  -d '{
    "sysCode": "crm",
    "sysName": "CRM客户管理系统",
    "sysType": "fullstack",
    "routePrefix": "/crm",
    "subAppEntry": "http://crm.company.com/entry.js",
    "adminUsername": "crm_admin",
    "adminPassword": "crm123"
  }'
```

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| sysCode | String | 是 | 系统唯一编码，如 `crm`、`erp` |
| sysName | String | 是 | 系统显示名称 |
| sysType | String | 是 | 接入类型，枚举：`backend`（仅后端接入）/ `frontend`（仅前端接入）/ `fullstack`（全栈接入） |
| routePrefix | String | 建议 | 网关路由前缀，如 `/crm`。backend/fullstack 类型建议填写 |
| subAppEntry | String | 条件必填 | 微前端子应用入口 URL。frontend/fullstack 类型必填 |
| adminUsername | String | 否 | 管理员用户名，不填则不自动创建管理员 |
| adminPassword | String | 否 | 管理员密码，不填且创建管理员则默认 `123456` |

**响应示例**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "sysCode": "crm",
    "apiKey": "a1b2c3d4e5f6789012345678abcdef01",
    "message": "注册成功",
    "apiDocsUrl": "http://gateway:8080/docs/接入指南.md"
  }
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| sysCode | String | 注册的系统编码 |
| apiKey | String | ⚠️ 系统 API Key（仅此一次返回），用于后续 API 鉴权 |
| message | String | 注册结果描述 |
| apiDocsUrl | String | 接入指南文档地址 |

> ⚠️ **apiKey 仅此一次返回，请妥善保存。** 丢失后需联系中台管理员重置。服务端仅存储 SHA-256 哈希值。

**错误响应**

```json
{
  "code": 500,
  "message": "系统编码已存在: crm",
  "data": null
}
```

---

### GET /api/registry/version — SDK 版本校验

客户端 SDK 启动时调用此接口校验版本兼容性。

**请求示例**

```bash
curl -X GET "http://localhost:8088/api/registry/version"
```

**响应示例**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "version": "1.0.0",
    "minSdkVersion": "1.0.0",
    "compatible": true
  }
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| version | String | 当前 API 版本号 |
| minSdkVersion | String | 最低兼容 SDK 版本 |
| compatible | Boolean | 当前 SDK 是否兼容 |

---

### GET /api/registry/system/{sysCode} — 查询注册状态

查询指定系统的注册信息。需通过 `X-Api-Key` Header 鉴权。

**请求示例**

```bash
curl -X GET "http://localhost:8088/api/registry/system/crm" \
  -H "X-Api-Key: a1b2c3d4e5f6789012345678abcdef01"
```

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| sysCode | String | 是 | 路径参数，系统编码 |
| X-Api-Key | String | 是 | Header 鉴权，注册时返回的 API Key |

**响应示例**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 1,
    "sysCode": "crm",
    "sysName": "CRM客户管理系统",
    "sysType": "fullstack",
    "routePrefix": "/crm",
    "subAppEntry": "http://crm.company.com/entry.js",
    "status": "0",
    "orderNum": 2
  }
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Long | 系统主键 ID |
| sysCode | String | 系统编码 |
| sysName | String | 系统名称 |
| sysType | String | 接入类型：backend / frontend / fullstack |
| routePrefix | String | 网关路由前缀 |
| subAppEntry | String | 微前端子应用入口 URL |
| status | String | 状态：0=正常 |
| orderNum | Integer | 排序号 |

> 注：apiKey 字段不返回（仅存储 SHA-256 哈希，不可逆）。

---

## 2. 认证 API

---

### POST /auth/login — 登录

使用用户名密码登录，返回 Access Token 和 Refresh Token。

**请求示例**

```bash
curl -X POST http://localhost:8088/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| username | String | 是 | 用户名 |
| password | String | 是 | 密码 |
| captcha | String | 否 | 验证码 |
| captchaKey | String | 否 | 验证码 Key |
| sysCode | String | 否 | 登录来源系统编码，Token 中会携带此字段 |

**响应示例**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "accessToken": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsInVzZXJJZCI6MSwic3lzQ29kZSI6Inl3dCIsImlhdCI6MTcxODQwMDAwMCwiZXhwIjoxNzE4NDA3MjAwfQ.xxx",
    "refreshToken": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsInVzZXJJZCI6MSwic3lzQ29kZSI6Inl3dCIsInR5cGUiOiJyZWZyZXNoIiwiaWF0IjoxNzE4NDAwMDAwLCJleHAiOjE3MTkwMDQ4MDB9.yyy",
    "expiresIn": 7200,
    "username": "admin",
    "nickname": "管理员",
    "avatar": "",
    "appList": [
      { "id": 1, "appName": "业务中台", "appCode": "ywt", "icon": "system" }
    ]
  }
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| accessToken | String | 访问令牌，有效期 2 小时，后续请求通过 `Authorization: Bearer <token>` 携带 |
| refreshToken | String | 刷新令牌，有效期 7 天，用于获取新 accessToken |
| expiresIn | Long | accessToken 过期秒数（7200） |
| username | String | 登录用户名 |
| nickname | String | 用户昵称 |
| avatar | String | 头像 URL |
| appList | Array | 用户可访问的应用列表 |

---

### POST /auth/refresh — Token 刷新

用 Refresh Token 换取新的 Access Token。支持两种传入方式。

**方式一：X-Refresh-Token Header（推荐）**

```bash
curl -X POST http://localhost:8088/auth/refresh \
  -H "X-Refresh-Token: eyJhbGciOiJIUzI1NiJ9..."
```

**方式二：Authorization Header（兼容旧版，用过期 accessToken 刷新，需在 7 天窗口内）**

```bash
curl -X POST http://localhost:8088/auth/refresh \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9..."
```

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| X-Refresh-Token | String | 二选一 | 专用 Refresh Token（推荐，7 天有效） |
| Authorization | String | 二选一 | 过期但未超 7 天的 Access Token（兼容旧版） |

**响应示例**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiJ9.new_access_token...",
    "expiresIn": 7200
  }
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| token | String | 新签发的 Access Token |
| expiresIn | Long | 过期秒数（7200） |

---

### POST /auth/logout — 退出登录

使当前 Access Token 失效。

```bash
curl -X POST http://localhost:8088/auth/logout \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9..."
```

---

## 3. 用户管理 API

> 以下接口均需 `Authorization: Bearer <token>` Header 鉴权。

---

### GET /system/user/list — 用户列表

分页查询用户。

**请求示例**

```bash
curl -X GET "http://localhost:8088/system/user/list?pageNum=1&pageSize=10&sysCode=ywt" \
  -H "Authorization: Bearer <token>"
```

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| pageNum | Integer | 否 | 页码，默认 1 |
| pageSize | Integer | 否 | 每页条数，默认 10 |
| username | String | 否 | 用户名筛选（模糊匹配） |
| status | String | 否 | 状态筛选：0=正常 1=停用 |
| deptId | Long | 否 | 部门 ID 筛选 |
| sysCode | String | 否 | 系统编码筛选 |

**响应示例**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "total": 50,
    "rows": [
      {
        "id": 1,
        "sysCode": "ywt",
        "deptId": 100,
        "username": "admin",
        "nickname": "管理员",
        "email": "admin@example.com",
        "phone": "13800138000",
        "sex": "1",
        "avatar": "",
        "status": "0",
        "delFlag": "0",
        "loginIp": "127.0.0.1",
        "loginDate": "2026-06-15T10:30:00"
      }
    ]
  }
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| total | Long | 总记录数 |
| rows | Array | 用户列表 |
| rows[].id | Long | 用户 ID |
| rows[].sysCode | String | 所属系统编码 |
| rows[].deptId | Long | 部门 ID |
| rows[].username | String | 用户名 |
| rows[].nickname | String | 昵称 |
| rows[].email | String | 邮箱 |
| rows[].phone | String | 手机号 |
| rows[].sex | String | 性别：0=男 1=女 2=未知 |
| rows[].status | String | 状态：0=正常 1=停用 |
| rows[].delFlag | String | 删除标记：0=正常 2=已删除 |

---

### GET /system/user/{id} — 用户详情

```bash
curl -X GET "http://localhost:8088/system/user/1" \
  -H "Authorization: Bearer <token>"
```

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | Long | 是 | 路径参数，用户 ID |

---

### POST /system/user — 创建用户

```bash
curl -X POST http://localhost:8088/system/user \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "username": "zhangsan",
    "password": "123456",
    "nickname": "张三",
    "deptId": 100,
    "email": "zhangsan@example.com",
    "phone": "13900139000",
    "sex": "1",
    "status": "0"
  }'
```

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| username | String | 是 | 用户名 |
| password | String | 是 | 密码 |
| nickname | String | 否 | 昵称 |
| deptId | Long | 否 | 部门 ID |
| email | String | 否 | 邮箱 |
| phone | String | 否 | 手机号 |
| sex | String | 否 | 性别 |
| status | String | 否 | 状态 |
| sysCode | String | 否 | 系统编码（不填则自动使用当前用户 sysCode） |

> 需要权限：`system:user:list`

---

### PUT /system/user — 更新用户

```bash
curl -X PUT http://localhost:8088/system/user \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "id": 1,
    "nickname": "管理员2",
    "email": "new@example.com"
  }'
```

请求体字段同创建用户，`id` 为必填。

> 需要权限：`system:user:list`

---

### DELETE /system/user/{ids} — 删除用户

```bash
curl -X DELETE "http://localhost:8088/system/user/2,3,4" \
  -H "Authorization: Bearer <token>"
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| ids | String | 是 | 路径参数，逗号分隔的用户 ID 列表 |

> 需要权限：`system:user:list`

---

### GET /system/user/{userId}/roles — 用户角色列表

返回指定用户已分配的角色 ID 列表。

```bash
curl -X GET "http://localhost:8088/system/user/1/roles" \
  -H "Authorization: Bearer <token>"
```

**响应示例**

```json
{
  "code": 200,
  "message": "操作成功",
  "data": [1, 2, 3]
}
```

---

### PUT /system/user/{userId}/roles — 分配角色

为指定用户分配角色（全量替换）。

```bash
curl -X PUT "http://localhost:8088/system/user/1/roles" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"roleIds": [1, 2]}'
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| userId | Long | 是 | 路径参数，用户 ID |
| roleIds | Array\<Integer\> | 是 | Body，角色 ID 列表 |

> 需要权限：`system:user:list`

---

### PUT /system/user/resetPwd — 重置密码

```bash
curl -X PUT http://localhost:8088/system/user/resetPwd \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"userId": 1, "password": "newPassword123"}'
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| userId | Long | 是 | Body，用户 ID |
| password | String | 是 | Body，新密码 |

> 需要权限：`system:user:list`

---

### GET /system/user/current — 当前登录用户信息

返回当前 Token 对应的用户信息、部门、角色。

```bash
curl -X GET "http://localhost:8088/system/user/current" \
  -H "Authorization: Bearer <token>"
```

**响应示例**

```json
{
  "code": 200,
  "data": {
    "user": { "id": 1, "username": "admin", "nickname": "管理员", "sysCode": "ywt" },
    "dept": { "id": 100, "deptName": "总公司" },
    "roles": [{ "id": 1, "roleName": "超级管理员", "roleKey": "admin" }]
  }
}
```

---

### GET /system/user/permissions — 当前用户权限列表

返回当前用户的所有权限标识符。

```bash
curl -X GET "http://localhost:8088/system/user/permissions" \
  -H "Authorization: Bearer <token>"
```

**响应示例**

```json
{
  "code": 200,
  "data": ["system:user:list", "system:role:list", "system:menu:list"]
}
```

---

## 4. 角色管理 API

---

### GET /system/role/list — 角色列表

```bash
curl -X GET "http://localhost:8088/system/role/list?sysCode=ywt" \
  -H "Authorization: Bearer <token>"
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| sysCode | String | 否 | 系统编码筛选 |

**响应示例**

```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "sysCode": "ywt",
      "roleName": "超级管理员",
      "roleKey": "admin",
      "roleSort": 1,
      "dataScope": "1",
      "status": "0",
      "delFlag": "0"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Long | 角色 ID |
| sysCode | String | 所属系统编码 |
| roleName | String | 角色名称 |
| roleKey | String | 角色权限标识 |
| roleSort | Integer | 排序 |
| dataScope | String | 数据范围：1=全部 2=自定义 3=本部门 4=本部门及以下 5=本人 |
| status | String | 状态：0=正常 1=停用 |

> 需要权限：`system:role:list`

---

### POST /system/role — 创建角色

```bash
curl -X POST http://localhost:8088/system/role \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "roleName": "普通用户",
    "roleKey": "user",
    "roleSort": 2,
    "dataScope": "1",
    "status": "0"
  }'
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| roleName | String | 是 | 角色名称 |
| roleKey | String | 是 | 角色权限标识 |
| roleSort | Integer | 否 | 排序 |
| dataScope | String | 否 | 数据范围 |
| status | String | 否 | 状态 |
| sysCode | String | 否 | 系统编码（不填则自动使用当前用户 sysCode） |

> 需要权限：`system:role:list`

---

### PUT /system/role — 更新角色

```bash
curl -X PUT http://localhost:8088/system/role \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"id": 2, "roleName": "普通用户2"}'
```

请求体同创建，`id` 必填。

> 需要权限：`system:role:list`

---

### DELETE /system/role/{ids} — 删除角色

```bash
curl -X DELETE "http://localhost:8088/system/role/3,4" \
  -H "Authorization: Bearer <token>"
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| ids | String | 是 | 路径参数，逗号分隔的角色 ID 列表 |

> 需要权限：`system:role:list`

---

### PUT /system/role/assignMenus — 角色分配菜单

```bash
curl -X PUT http://localhost:8088/system/role/assignMenus \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"roleId": 2, "menuIds": [101, 102, 103]}'
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| roleId | Long | 是 | Body，角色 ID |
| menuIds | Array\<Integer\> | 是 | Body，菜单 ID 列表 |

> 需要权限：`system:role:list`

---

## 5. 菜单管理 API

---

### GET /system/menu/list — 菜单列表

返回树形结构的菜单数据，支持按系统编码和应用筛选。

```bash
curl -X GET "http://localhost:8088/system/menu/list?sysCode=ywt" \
  -H "Authorization: Bearer <token>"
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| sysCode | String | 否 | 系统编码筛选 |
| appId | Long | 否 | 应用 ID 筛选 |

**响应示例**

```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "sysCode": "ywt",
      "menuName": "系统管理",
      "parentId": 0,
      "orderNum": 1,
      "path": "/system",
      "component": "",
      "menuType": "M",
      "visible": "0",
      "status": "0",
      "perms": "",
      "icon": "system",
      "children": [
        {
          "id": 2,
          "menuName": "用户管理",
          "parentId": 1,
          "path": "/system/user",
          "menuType": "C",
          "perms": "system:user:list",
          "children": []
        }
      ]
    }
  ]
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Long | 菜单 ID |
| sysCode | String | 所属系统编码 |
| menuName | String | 菜单名称 |
| parentId | Long | 父菜单 ID，0 为根节点 |
| orderNum | Integer | 排序号 |
| path | String | 路由路径 |
| component | String | 前端组件路径 |
| menuType | String | 菜单类型：M=目录 C=菜单 F=按钮 |
| visible | String | 是否显示：0=显示 1=隐藏 |
| status | String | 状态：0=正常 1=停用 |
| perms | String | 权限标识 |
| icon | String | 图标 |
| children | Array | 子菜单列表 |

---

### POST /system/menu — 创建菜单

```bash
curl -X POST http://localhost:8088/system/menu \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "menuName": "订单管理",
    "parentId": 0,
    "orderNum": 2,
    "path": "/order",
    "menuType": "M",
    "visible": "0",
    "status": "0",
    "icon": "order"
  }'
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| menuName | String | 是 | 菜单名称 |
| parentId | Long | 是 | 父菜单 ID |
| orderNum | Integer | 否 | 排序号 |
| path | String | 否 | 路由路径 |
| component | String | 否 | 前端组件路径 |
| menuType | String | 是 | M=目录 C=菜单 F=按钮 |
| visible | String | 否 | 是否显示 |
| status | String | 否 | 状态 |
| perms | String | 否 | 权限标识 |
| icon | String | 否 | 图标 |
| sysCode | String | 否 | 系统编码（不填自动使用当前用户 sysCode） |

> 需要权限：`system:menu:list`

---

### PUT /system/menu — 更新菜单

```bash
curl -X PUT http://localhost:8088/system/menu \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"id": 10, "menuName": "订单管理2"}'
```

> 需要权限：`system:menu:list`

---

### DELETE /system/menu/{id} — 删除菜单

```bash
curl -X DELETE "http://localhost:8088/system/menu/10" \
  -H "Authorization: Bearer <token>"
```

> 需要权限：`system:menu:list`

---

## 6. 部门管理 API

---

### GET /system/dept/list — 部门列表

返回树形结构的部门数据。

```bash
curl -X GET "http://localhost:8088/system/dept/list?sysCode=ywt" \
  -H "Authorization: Bearer <token>"
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| sysCode | String | 否 | 系统编码筛选 |

**响应示例**

```json
{
  "code": 200,
  "data": [
    {
      "id": 100,
      "sysCode": "ywt",
      "parentId": 0,
      "ancestors": "0",
      "deptName": "总公司",
      "orderNum": 0,
      "leader": "张经理",
      "phone": "010-12345678",
      "email": "hr@example.com",
      "status": "0",
      "delFlag": "0"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Long | 部门 ID |
| sysCode | String | 所属系统编码 |
| parentId | Long | 父部门 ID，0 为根节点 |
| ancestors | String | 祖级列表 |
| deptName | String | 部门名称 |
| orderNum | Integer | 排序号 |
| leader | String | 负责人 |
| phone | String | 联系电话 |
| email | String | 邮箱 |
| status | String | 状态：0=正常 1=停用 |

---

### POST /system/dept — 创建部门

```bash
curl -X POST http://localhost:8088/system/dept \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "parentId": 100,
    "deptName": "研发部",
    "orderNum": 1,
    "leader": "李工",
    "status": "0"
  }'
```

---

### PUT /system/dept — 更新部门

```bash
curl -X PUT http://localhost:8088/system/dept \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"id": 101, "deptName": "研发中心"}'
```

---

### DELETE /system/dept/{id} — 删除部门

```bash
curl -X DELETE "http://localhost:8088/system/dept/101" \
  -H "Authorization: Bearer <token>"
```

---

## 7. 字典管理 API

---

### GET /system/dict/type/all — 全部字典类型

返回所有启用的字典类型列表。

```bash
curl -X GET "http://localhost:8088/system/dict/type/all" \
  -H "Authorization: Bearer <token>"
```

**响应示例**

```json
{
  "code": 200,
  "data": [
    { "id": 1, "sysCode": "ywt", "dictName": "用户性别", "dictType": "sys_user_sex", "status": "0" }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Long | 字典类型 ID |
| sysCode | String | 所属系统编码 |
| dictName | String | 字典名称 |
| dictType | String | 字典类型标识 |
| status | String | 状态 |

---

### GET /system/dict/data/list — 字典数据列表

按字典类型分页查询字典数据。

```bash
curl -X GET "http://localhost:8088/system/dict/data/list?pageNum=1&pageSize=10&dictType=sys_user_sex" \
  -H "Authorization: Bearer <token>"
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| pageNum | Integer | 否 | 页码，默认 1 |
| pageSize | Integer | 否 | 每页条数，默认 10 |
| dictType | String | 否 | 字典类型标识筛选 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 3,
    "rows": [
      { "id": 1, "dictSort": 0, "dictLabel": "男", "dictValue": "0", "dictType": "sys_user_sex", "status": "0" },
      { "id": 2, "dictSort": 1, "dictLabel": "女", "dictValue": "1", "dictType": "sys_user_sex", "status": "0" }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| dictSort | Integer | 排序 |
| dictLabel | String | 显示标签 |
| dictValue | String | 数据值 |
| dictType | String | 字典类型标识 |
| isDefault | String | 是否默认 |
| status | String | 状态 |

---

### GET /system/dict/data/type/{dictType} — 按类型获取字典数据

一次性获取某类型下所有启用的字典数据（不分页）。

```bash
curl -X GET "http://localhost:8088/system/dict/data/type/sys_user_sex" \
  -H "Authorization: Bearer <token>"
```

---

## 8. 操作日志 API

---

### GET /system/operlog/list — 操作日志列表

分页查询操作日志。

```bash
curl -X GET "http://localhost:8088/system/operlog/list?pageNum=1&pageSize=10&sysCode=ywt" \
  -H "Authorization: Bearer <token>"
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| pageNum | Integer | 否 | 页码，默认 1 |
| pageSize | Integer | 否 | 每页条数，默认 10 |
| title | String | 否 | 操作标题（模糊匹配） |
| operName | String | 否 | 操作人姓名 |
| status | String | 否 | 操作状态：0=成功 1=失败 |
| sysCode | String | 否 | 系统编码 |
| startTime | DateTime | 否 | 开始时间（ISO 格式） |
| endTime | DateTime | 否 | 结束时间（ISO 格式） |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 100,
    "rows": [
      {
        "id": 1,
        "title": "新增用户",
        "operName": "admin",
        "requestMethod": "POST",
        "operUrl": "/system/user",
        "operIp": "127.0.0.1",
        "operParam": "{\"username\":\"zhangsan\"}",
        "status": "0",
        "costTime": 45,
        "sysCode": "ywt",
        "operTime": "2026-06-15T10:30:00"
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Long | 日志 ID |
| title | String | 操作标题 |
| operName | String | 操作人 |
| requestMethod | String | 请求方法 |
| operUrl | String | 请求 URL |
| operIp | String | 操作 IP |
| operParam | String | 请求参数 JSON |
| jsonResult | String | 响应结果 JSON |
| status | String | 状态：0=成功 1=失败 |
| errorMsg | String | 错误信息（失败时） |
| costTime | Integer | 耗时（毫秒） |
| sysCode | String | 系统编码 |
| operTime | DateTime | 操作时间 |

> 需要权限：`monitor:operlog:list`

---

### DELETE /system/operlog/batch — 批量删除操作日志

按时间范围批量删除。

```bash
curl -X DELETE "http://localhost:8088/system/operlog/batch?startTime=2026-01-01T00:00:00&endTime=2026-06-01T00:00:00" \
  -H "Authorization: Bearer <token>"
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| startTime | DateTime | 否 | 开始时间（不填则无下限） |
| endTime | DateTime | 否 | 结束时间（不填则无上限） |

> 需要权限：`monitor:operlog:remove`

---

### DELETE /system/operlog/clean — 清空操作日志

```bash
curl -X DELETE "http://localhost:8088/system/operlog/clean" \
  -H "Authorization: Bearer <token>"
```

> 需要权限：`monitor:operlog:remove`

---

## 9. 登录日志 API

---

### GET /system/loginlog/list — 登录日志列表

分页查询登录日志。

```bash
curl -X GET "http://localhost:8088/system/loginlog/list?pageNum=1&pageSize=10&sysCode=ywt" \
  -H "Authorization: Bearer <token>"
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| pageNum | Integer | 否 | 页码，默认 1 |
| pageSize | Integer | 否 | 每页条数，默认 10 |
| username | String | 否 | 用户名筛选 |
| status | String | 否 | 登录状态：0=成功 1=失败 |
| sysCode | String | 否 | 系统编码 |
| startTime | DateTime | 否 | 开始时间 |
| endTime | DateTime | 否 | 结束时间 |

**响应示例**

```json
{
  "code": 200,
  "data": {
    "total": 50,
    "rows": [
      {
        "id": 1,
        "username": "admin",
        "ipaddr": "127.0.0.1",
        "loginLocation": "内网IP",
        "browser": "Chrome 120",
        "os": "Windows 10",
        "status": "0",
        "msg": "登录成功",
        "sysCode": "ywt",
        "loginTime": "2026-06-15T10:30:00"
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Long | 日志 ID |
| username | String | 登录用户名 |
| ipaddr | String | 登录 IP |
| loginLocation | String | 登录地点 |
| browser | String | 浏览器 |
| os | String | 操作系统 |
| status | String | 状态：0=成功 1=失败 |
| msg | String | 提示信息 |
| sysCode | String | 系统编码 |
| loginTime | DateTime | 登录时间 |

> 需要权限：`monitor:loginlog:list`

---

### DELETE /system/loginlog/batch — 批量删除登录日志

```bash
curl -X DELETE "http://localhost:8088/system/loginlog/batch?startTime=2026-01-01T00:00:00&endTime=2026-06-01T00:00:00" \
  -H "Authorization: Bearer <token>"
```

> 需要权限：`monitor:loginlog:remove`

---

### DELETE /system/loginlog/clean — 清空登录日志

```bash
curl -X DELETE "http://localhost:8088/system/loginlog/clean" \
  -H "Authorization: Bearer <token>"
```

> 需要权限：`monitor:loginlog:remove`

---

## 10. 通用说明

### 认证方式

| 场景 | 认证方式 |
|------|---------|
| 用户接口（/auth/*, /system/*） | `Authorization: Bearer <accessToken>` Header |
| 子系统自注册接口（/api/registry/system） | 无需认证 |
| 子系统查询接口（/api/registry/system/{sysCode}） | `X-Api-Key: <apiKey>` Header |

### Token 生命周期

| Token 类型 | 有效期 | 说明 |
|-----------|--------|------|
| Access Token | 2 小时 | 用于日常 API 调用，通过 `Authorization: Bearer` 携带 |
| Refresh Token | 7 天 | 用于刷新 Access Token，通过 `X-Refresh-Token` 携带 |
| Access Token 最大刷新窗口 | 7 天 | 旧版兼容模式：过期 accessToken 在 7 天内可刷新 |

### 通用响应格式

```json
{
  "code": 200,
  "message": "操作成功",
  "data": { ... }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| code | Integer | 状态码 |
| message | String | 提示信息 |
| data | Object/Array/Null | 响应数据 |

### 分页响应格式

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "total": 100,
    "rows": [ ... ]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| total | Long | 总记录数 |
| rows | Array | 当前页数据列表 |

### 通用分页参数

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| pageNum | Integer | 1 | 页码（从 1 开始） |
| pageSize | Integer | 10 | 每页记录数 |

### 通用错误码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 401 | 未认证 / Token 过期 / API Key 无效 |
| 403 | 无权限 |
| 500 | 系统错误 |

### 多系统隔离

所有业务实体（用户、角色、菜单、部门、字典等）均带 `sysCode` 字段用于多系统数据隔离：

- **ywt 系统**：中台自身的管理员可见所有系统数据
- **子系统**：用户只能看到和操作本系统的数据（创建时自动注入当前用户 `sysCode`）
- **自注册系统**：注册时创建的角色/菜单/用户自动绑定对应 `sysCode`

### 服务架构

```
外部请求 → Gateway (8088) → [Auth(8100) / System(8200) / Platform(8300) / AI(8400)]

内部端口（不直接对外）：
  8100 — yewuzhongtai-auth（认证服务）
  8200 — yewuzhongtai-system（系统管理服务）
  8300 — yewuzhongtai-platform（平台服务）
  8400 — yewuzhongtai-ai（AI 服务）
```

所有外部请求统一通过网关 `localhost:8088` 访问。
