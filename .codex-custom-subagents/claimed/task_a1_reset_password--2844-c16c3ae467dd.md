# Codex Custom Subagents task handoff v1

Task: task_a1_reset_password

## 任务：后端管理员重置密码接口（易用性优化计划 A 任务 1）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成 TDD 实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

这是 git 分支 `codex/usability-overhaul` 的隔离 worktree，基线 `4ec3523`。启动时 `cd` 到该目录，`git status` 确认干净。

### 步骤 1：编写失败的测试

新建 `backend/tests/test_admin_user_reset_password.py`：

```python
import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.routers.admin_users import reset_user_password
from app.schemas.role import AdminResetPassword


def test_reset_password_schema_rejects_short_password():
    with pytest.raises(Exception):
        AdminResetPassword(new_password="123")


def test_reset_password_accepts_valid_password():
    data = AdminResetPassword(new_password="newpass123")
    assert data.new_password == "newpass123"


def test_reset_password_raises_404_when_user_missing():
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    with pytest.raises(Exception) as exc:
        asyncio.run(reset_user_password("u1", AdminResetPassword(new_password="newpass123"), _=None, db=db))
    assert exc.value.status_code == 404


def test_reset_password_updates_hash():
    from app.services.auth_service import verify_password

    db = AsyncMock()
    user = MagicMock()
    user.password_hash = None
    db.execute.return_value.scalar_one_or_none.return_value = user
    asyncio.run(reset_user_password("u1", AdminResetPassword(new_password="newpass123"), _=None, db=db))
    assert verify_password("newpass123", user.password_hash)
    db.commit.assert_awaited_once()
```

### 步骤 2：运行测试验证失败

运行：`cd backend && python -m pytest tests/test_admin_user_reset_password.py -v`

预期：FAIL，报错 `ImportError: cannot import name 'reset_user_password'` 与 `AdminResetPassword` 未定义。

### 步骤 3：实现 schema 与路由

在 `backend/app/schemas/role.py` 的 `AdminUserUpdate` 之后追加：

```python
class AdminResetPassword(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)
```

在 `backend/app/routers/admin_users.py` 的 `delete_user` 之后追加：

```python
@router.post("/{user_id}/reset-password", response_model=ApiResponse[AdminUserResponse])
async def reset_user_password(
    user_id: str,
    data: AdminResetPassword,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    user.password_hash = hash_password(data.new_password)
    await db.commit()
    await db.refresh(user)
    return ApiResponse(data=AdminUserResponse.model_validate(user))
```

同时更新 `admin_users.py` 顶部导入：`from app.schemas.role import AdminUserCreate, AdminUserUpdate, AdminUserResponse, AdminResetPassword`。

### 步骤 4：运行测试验证通过

运行：`cd backend && python -m pytest tests/test_admin_user_reset_password.py -v`

预期：4 个测试全部 PASS。

### 步骤 5：全量回归（尽力而为）

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS（若环境原因无法全量运行，至少运行本任务测试文件并说明）。

### 步骤 6：Commit

```bash
git add backend/app/schemas/role.py backend/app/routers/admin_users.py backend/tests/test_admin_user_reset_password.py
git commit -m "feat(admin): add reset password endpoint for admin users"
```

## 上下文

- 这是易用性整体优化的基础层第一个任务，后端先行。后续任务（前端重置密码弹窗）依赖本任务接口。
- 现有代码：`backend/app/routers/admin_users.py` 已有 list/get/create/update/delete 用户路由，使用 `require_admin` 依赖、`hash_password`（来自 `app.services.auth_service`）、`AdminUserResponse`、`ApiResponse`；`backend/app/schemas/role.py` 已有 AdminUserCreate/Update/Response。
- 测试风格：项目后端测试为纯单元测试（不连数据库），用 MagicMock/AsyncMock 模拟 db，用 `asyncio.run` 跑 async 路由函数，从 `backend/` 目录执行 pytest（conftest.py 已处理 sys.path）。
- 注意：若 `AdminResetPassword` 导入顺序导致路由文件顶部 import 冲突，按现有导入风格调整；不要改动本任务范围之外的文件。

## 开始之前

如果对需求/方案/依赖有任何不清楚的地方，**现在就问**（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 严格按任务描述实现（TDD 顺序：先测试 → 验证失败 → 实现 → 验证通过）
2. 运行测试确认（见步骤 2/4/5）
3. 按任务描述提交
4. 自审（完整性/质量/纪律/测试），发现的问题在汇报前修复
5. 汇报

**工作过程中遇到意外或不清楚的情况，提问，不要猜测。**

## 汇报格式

- **状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 实现了什么、测试了什么及结果、修改了哪些文件、自审发现、任何疑虑
