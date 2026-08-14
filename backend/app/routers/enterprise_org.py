from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.enterprise_org import (
    MemberCreate,
    MemberResponse,
    MemberUpdate,
    OrgTreeUpdate,
)
from app.services.enterprise_org_service import (
    IMPORT_HEADERS,
    parse_member_rows,
    sync_org_structure,
    validate_org_tree,
)

router = APIRouter(prefix="/enterprises/{enterprise_id}/org", tags=["Enterprise Org"])

MAX_IMPORT_SIZE = 5 * 1024 * 1024  # 5MB


async def _get_ent(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
    """读路径企业归属校验：企业存在且属于当前用户。

    契约要求读权限放开给登录用户（企业主或成员），但本项目企业均为单个
    user 所有、尚无成员归属关系，因此读写统一按
    enterprise.user_id == current_user.id 校验归属（成员场景后续扩展）。
    """
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == user_id)
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    return ent


async def _get_owned_ent(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
    """写路径：企业不存在 → 404；存在但非当前用户所有 → 403（仅企业主可写）。"""
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    if ent.user_id != user_id:
        raise HTTPException(403, "无权限操作该企业")
    return ent


async def _get_member(enterprise_id: str, member_id: str, db: AsyncSession) -> EnterpriseMember:
    member = (await db.execute(
        select(EnterpriseMember).where(
            EnterpriseMember.id == member_id,
            EnterpriseMember.enterprise_id == enterprise_id,
        )
    )).scalar_one_or_none()
    if not member:
        raise HTTPException(404, "成员不存在")
    return member


def _next_org_node_id(nodes: list) -> str:
    """生成不与现有节点冲突的 node-<n> 短 id（对齐 normalize_org_nodes 规则）。"""
    existing = {n.get("id") for n in nodes if isinstance(n, dict)}
    i = 1
    while f"node-{i}" in existing:
        i += 1
    return f"node-{i}"


def _find_or_create_org_node(nodes: list, node_type: str, name: str, parent_id: str | None) -> str | None:
    """按名称在同层查找节点，找不到则创建（id 复用 normalize 短 id 规则）。"""
    if not name:
        return None
    for n in nodes:
        if (
            isinstance(n, dict)
            and n.get("type") == node_type
            and n.get("name") == name
            and n.get("parent_id") == parent_id
        ):
            return n["id"]
    node_id = _next_org_node_id(nodes)
    nodes.append({"id": node_id, "type": node_type, "name": name, "parent_id": parent_id, "members": []})
    return node_id


def _build_org_path(node_id: str | None, nodes: dict) -> str:
    """沿 parent_id 从节点向上拼 部门/班组 路径（无节点时为空串）。"""
    if not node_id or node_id not in nodes:
        return ""
    parts = []
    cur = node_id
    seen = set()
    while cur and cur in nodes and cur not in seen:
        seen.add(cur)
        parts.append(nodes[cur].get("name", ""))
        cur = nodes[cur].get("parent_id")
    return "/".join(reversed([p for p in parts if p]))


@router.get("/nodes", response_model=ApiResponse[list])
async def get_org_nodes(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = await _get_ent(enterprise_id, current_user.id, db)
    return ApiResponse(data=ent.org_structure or [])


@router.put("/nodes", response_model=ApiResponse[list])
async def update_org_nodes(
    enterprise_id: str,
    body: OrgTreeUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ent = await _get_owned_ent(enterprise_id, current_user.id, db)
    nodes = [n.model_dump() for n in body.nodes]
    errors = validate_org_tree(nodes)
    if errors:
        raise HTTPException(
            422,
            detail={
                "code": "ORG_TREE_INVALID",
                "errors": errors,
                "message": "；".join(errors),
            },
        )
    sync_org_structure(ent, nodes)
    await db.commit()
    return ApiResponse(data=ent.org_structure)


@router.post("/members", response_model=ApiResponse[MemberResponse], status_code=201)
async def create_member(
    enterprise_id: str,
    body: MemberCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await _get_owned_ent(enterprise_id, current_user.id, db)
    user = (await db.execute(select(User).where(User.id == body.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    exists = (await db.execute(
        select(EnterpriseMember.id).where(
            EnterpriseMember.enterprise_id == enterprise_id,
            EnterpriseMember.user_id == body.user_id,
        )
    )).first()
    if exists:
        raise HTTPException(409, "该用户已是企业成员")
    member = EnterpriseMember(enterprise_id=enterprise_id, **body.model_dump(exclude_none=True))
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return ApiResponse(data=MemberResponse.model_validate(member))


@router.put("/members/{member_id}", response_model=ApiResponse[MemberResponse])
async def update_member(
    enterprise_id: str,
    member_id: str,
    body: MemberUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await _get_owned_ent(enterprise_id, current_user.id, db)
    member = await _get_member(enterprise_id, member_id, db)
    updates = body.model_dump(exclude_unset=True)
    # role/enabled 为 NOT NULL 列，显式 null 会导致提交时 500，直接拒绝；
    # position/org_node_id 保留显式 null 的清空语义。
    for key in ("role", "enabled"):
        if key in updates and updates[key] is None:
            raise HTTPException(422, f"{key} 不能为 null")
    for key, value in updates.items():
        setattr(member, key, value)
    await db.commit()
    await db.refresh(member)
    return ApiResponse(data=MemberResponse.model_validate(member))


@router.delete("/members/{member_id}")
async def delete_member(
    enterprise_id: str,
    member_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await _get_owned_ent(enterprise_id, current_user.id, db)
    member = await _get_member(enterprise_id, member_id, db)
    # 成员绑定解除采用硬删，避免历史成员残留（成员列表按 enterprise_id 查询，
    # 软删 enabled=false 会使列表/状态逻辑复杂化）；如需审计留痕再改软删。
    await db.delete(member)
    await db.commit()
    return {"code": 0, "message": "已删除"}


@router.get("/members", response_model=ApiResponse[list[MemberResponse]])
async def list_members(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await _get_ent(enterprise_id, current_user.id, db)
    rows = (await db.execute(
        select(EnterpriseMember, User)
        .join(User, User.id == EnterpriseMember.user_id)
        .where(EnterpriseMember.enterprise_id == enterprise_id)
        .order_by(EnterpriseMember.created_at)
    )).all()
    items = [
        MemberResponse(
            id=m.id,
            enterprise_id=m.enterprise_id,
            user_id=m.user_id,
            email=u.email,
            name=u.name,
            org_node_id=m.org_node_id,
            position=m.position,
            role=m.role,
            enabled=m.enabled,
        )
        for m, u in rows
    ]
    return ApiResponse(data=items)


@router.post("/members/import")
async def import_members(
    enterprise_id: str,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Excel 批量导入成员：按邮箱绑定已有账号，部门/班组名查或建节点。"""
    ent = await _get_owned_ent(enterprise_id, current_user.id, db)
    content = await file.read()
    if len(content) > MAX_IMPORT_SIZE:
        raise HTTPException(413, "导入文件过大，请使用 5MB 以内的模板文件")
    # 非 xlsx/损坏文件会抛 InvalidFileException/BadZipFile/解析类异常，统一 400；
    # 与 file_parser 的宽异常兜底惯例一致，避免裸 500。
    try:
        wb = load_workbook(BytesIO(content), data_only=True)
    except Exception:
        raise HTTPException(400, "导入文件格式无效，请使用模板")
    ws = wb.active
    # 表头须与模板一致（忽略顺序、去空白），避免整表误报「邮箱必填」
    headers = ["" if c.value is None else str(c.value).strip() for c in ws[1]]
    if sorted(headers) != sorted(IMPORT_HEADERS):
        raise HTTPException(400, "表头与模板不符，请使用模板")
    raw_rows: list[tuple[int, dict]] = []
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        raw_rows.append((idx, dict(zip(headers, row))))

    parsed = parse_member_rows([r for _, r in raw_rows])
    imported = 0
    skipped = 0
    errors: list[dict] = []
    imported_user_ids: set[str] = set()
    nodes = list(ent.org_structure or [])
    for (row_num, _), item in zip(raw_rows, parsed):
        if item.get("error"):
            errors.append({"row": row_num, "reason": item["error"]})
            continue
        user = (await db.execute(select(User).where(User.email == item["email"]))).scalar_one_or_none()
        if not user:
            errors.append({"row": row_num, "reason": f"用户不存在: {item['email']}"})
            continue
        # 文件内重复邮箱：提交前 DB 查询看不到本批未 flush 的成员，需请求内去重
        if user.id in imported_user_ids:
            skipped += 1
            continue
        exists = (await db.execute(
            select(EnterpriseMember.id).where(
                EnterpriseMember.enterprise_id == enterprise_id,
                EnterpriseMember.user_id == user.id,
            )
        )).first()
        if exists:
            skipped += 1
            continue
        dept_id = _find_or_create_org_node(nodes, "dept", item["department"], None)
        team_id = _find_or_create_org_node(nodes, "team", item["team"], dept_id) if item["team"] else None
        db.add(EnterpriseMember(
            enterprise_id=enterprise_id,
            user_id=user.id,
            org_node_id=team_id or dept_id,
            position=item["position"] or None,
            role=item["role"],
        ))
        imported += 1
        imported_user_ids.add(user.id)

    ent.org_structure = nodes
    await db.commit()
    return ApiResponse(data={"imported": imported, "skipped": skipped, "errors": errors})


@router.get("/members/available", response_model=ApiResponse[list])
async def get_available_members(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """返回启用成员（含 org_path），供隐患模块责任人选择器复用。"""
    ent = await _get_ent(enterprise_id, current_user.id, db)
    rows = (await db.execute(
        select(EnterpriseMember, User)
        .join(User, User.id == EnterpriseMember.user_id)
        .where(
            EnterpriseMember.enterprise_id == enterprise_id,
            EnterpriseMember.enabled.is_(True),
        )
        .order_by(EnterpriseMember.created_at)
    )).all()
    nodes = {n.get("id"): n for n in (ent.org_structure or []) if isinstance(n, dict)}
    items = [
        {
            "id": m.id,
            "name": u.name,
            "email": u.email,
            "role": m.role,
            "position": m.position,
            "org_path": _build_org_path(m.org_node_id, nodes),
        }
        for m, u in rows
    ]
    return ApiResponse(data=items)
