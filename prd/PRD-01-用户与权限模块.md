# PRD-01：用户与权限模块

> **版本**：1.0 | **创建日期**：2026-06-05 | **依赖**：PRD-00

---

## 1. 模块概述

提供用户注册、登录认证、Token 管理和个人信息维护功能。所有业务接口依赖 JWT 认证中间件进行身份校验和用户隔离。

**核心流程**：注册 → 登录获取 Token → 访问业务接口 → Token 过期自动刷新 → 退出登录

---

## 2. 数据模型

### 2.1 users 表

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL DEFAULT '''',
    role VARCHAR(20) NOT NULL DEFAULT ''user'' CHECK (role IN (''user'', ''admin'')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
```

### 2.2 refresh_tokens 表

```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);
```

### 2.3 Pydantic Schema

```python
# 请求
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    password_confirm: str
    name: str = Field(..., min_length=1, max_length=100)

    @validator(''password_confirm'')
    def passwords_match(cls, v, values):
        if ''password'' in values and v != values[''password'']:
            raise ValueError(''两次密码不一致'')
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class UpdateProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
    new_password_confirm: str

# 响应
class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒
```

---

## 3. API 接口

### 3.1 注册

```
POST /api/v1/auth/register
```

**请求体**：
```json
{
  "email": "user@example.com",
  "password": "Abc12345",
  "password_confirm": "Abc12345",
  "name": "张三"
}
```

**校验规则**：
- email：合法邮箱格式，未被注册（含已软删除的）
- password：≥8 位，必须包含字母和数字
- password_confirm：与 password 一致
- name：1-100 字符

**成功响应** (201)：
```json
{
  "code": 0,
  "message": "注册成功",
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "张三",
    "role": "user",
    "created_at": "2026-06-05T00:00:00Z"
  }
}
```

**错误响应**：
- `10001`：邮箱已被注册
- `10002`：密码不符合要求
- `10003`：两次密码不一致

### 3.2 登录

```
POST /api/v1/auth/login
```

**请求体**：
```json
{
  "email": "user@example.com",
  "password": "Abc12345"
}
```

**处理逻辑**：
1. 查找用户（排除软删除）
2. 验证密码 hash
3. 生成 access_token（2h）+ refresh_token（7d）
4. refresh_token 存入 `refresh_tokens` 表（存储其 SHA-256 hash）
5. 返回两个 token 给前端

**成功响应** (200)：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "dGhpcyBpcyBh...",
    "token_type": "bearer",
    "expires_in": 7200
  }
}
```

**错误响应**：
- `10004`：邮箱或密码错误
- `10005`：账号已被禁用

### 3.3 刷新 Token

```
POST /api/v1/auth/refresh
```

**请求体**：
```json
{
  "refresh_token": "dGhpcyBpcyBh..."
}
```

**处理逻辑**：
1. 计算 refresh_token 的 SHA-256 hash，查 `refresh_tokens` 表
2. 验证未过期、未撤销
3. 撤销旧 refresh_token（标记 `revoked = TRUE`）
4. 签发新的 access_token 和 refresh_token
5. 新 refresh_token 入库

**成功响应** (200)：同登录

**错误响应**：
- `10006`：refresh_token 无效或已过期

### 3.4 退出登录

```
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
```

**处理逻辑**：
1. 从当前用户的所有 refresh_token 全部标记 `revoked = TRUE`
2. 或者仅撤销请求中携带的 refresh_token

**请求体（可选）**：
```json
{
  "refresh_token": "dGhpcyBpcyBh..."
}
```

**成功响应** (200)：
```json
{
  "code": 0,
  "message": "已退出登录"
}
```

### 3.5 获取个人信息

```
GET /api/v1/users/me
Authorization: Bearer <access_token>
```

**响应**：`UserResponse`

### 3.6 更新个人信息

```
PUT /api/v1/users/me
Authorization: Bearer <access_token>
```

**请求体**：
```json
{
  "name": "张三丰"
}
```

### 3.7 修改密码

```
PUT /api/v1/users/me/password
Authorization: Bearer <access_token>
```

**请求体**：
```json
{
  "old_password": "Abc12345",
  "new_password": "Xyz67890",
  "new_password_confirm": "Xyz67890"
}
```

**校验规则**：
- old_password 必须与当前密码一致
- new_password 不能与 old_password 相同
- new_password ≥8 位，含字母和数字
- new_password_confirm 一致

**成功响应**：清除用户所有 refresh_token，前端引导重新登录。

**错误响应**：
- `10007`：原密码错误

---

## 4. JWT 认证中间件

### 4.1 Token 结构

**access_token payload**：
```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "role": "user",
  "type": "access",
  "iat": 1717600000,
  "exp": 1717607200
}
```

**refresh_token**：64 字节随机字符串，不编码 payload，服务端通过 hash 匹配。

### 4.2 中间件实现要点

```python
# app/api/deps.py
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """从 JWT 提取用户，验证有效性，返回 User 对象。
    所有需认证的路由依赖此函数。
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise CREDENTIALS_EXCEPTION
    except JWTError:
        raise CREDENTIALS_EXCEPTION

    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise CREDENTIALS_EXCEPTION
    return user
```

### 4.3 前端 Token 管理

```typescript
// services/api.ts
const api = axios.create({ baseURL: ''/api/v1'' });

// 请求拦截器：自动注入 access_token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(''access_token'');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 响应拦截器：401 时自动刷新
api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      const refreshToken = localStorage.getItem(''refresh_token'');
      const { data } = await axios.post(''/api/v1/auth/refresh'', { refresh_token: refreshToken });
      localStorage.setItem(''access_token'', data.data.access_token);
      localStorage.setItem(''refresh_token'', data.data.refresh_token);
      error.config.headers.Authorization = `Bearer ${data.data.access_token}`;
      return api(error.config);
    }
    return Promise.reject(error);
  }
);
```

---

## 5. 前端页面

### 5.1 登录页

- 左侧：系统 Logo + 名称 + 简介
- 右侧：登录表单（邮箱、密码、登录按钮）
- 底部链接："没有账号？立即注册"
- 记住密码（本地存储邮箱，不存密码）
- 登录中 Loading 状态，按钮禁用
- 错误提示：红色 Alert

### 5.2 注册页

- 表单：姓名、邮箱、密码、确认密码
- 密码规则实时提示（≥8 位、含字母和数字）
- 注册成功 → 自动登录 → 跳转工作台
- 底部链接："已有账号？去登录"

### 5.3 个人信息页（设置内）

- 显示当前姓名、邮箱（邮箱只读）
- 修改姓名表单
- 修改密码表单（原密码、新密码、确认新密码）

---

## 6. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC01 | 注册成功后可登录 | 自动化：注册 → 登录 → 200 + Token |
| AC02 | 重复邮箱注册被拒绝，错误码 10001 | 自动化：同邮箱注册两次 → 400 |
| AC03 | 密码<8 位注册被拒绝 | 自动化：短密码注册 → 422 |
| AC04 | 错误密码登录被拒绝，错误码 10004 | 自动化：正确邮箱+错误密码 → 401 |
| AC05 | 登录获取有效 Token | 自动化：登录 → 用 access_token 访问 /users/me → 200 |
| AC06 | Token 过期后刷新 | 自动化：等 2h 或手动设短过期 → 401 → refresh → 新 Token 可用 |
| AC07 | 退出后 refresh_token 失效 | 自动化：退出 → refresh → 401 |
| AC08 | 修改密码后旧 Token 失效 | 自动化：改密码 → 旧 refresh_token → 401 |
| AC09 | 未登录访问业务接口返回 401 | 自动化：无 Token 访问 /enterprises → 401 |
| AC10 | 用户只能看到自己的数据 | 自动化：用户 A 创建企业 → 用户 B 访问 → 404 |

---

## 7. 安全约束

- 登录失败 5 次后，该邮箱 15 分钟内禁止登录（速率限制，Redis 实现）
- 密码哈希：bcrypt，cost factor = 12
- refresh_token 存储 SHA-256 hash，不存原始值
- 密码修改后，该用户所有 refresh_token 立即撤销
- 日志不记录密码明文和 Token
