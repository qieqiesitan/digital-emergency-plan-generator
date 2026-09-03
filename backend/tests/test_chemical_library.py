import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.chemical_library import ChemicalLibrary
from app.models.enterprise import Enterprise
from app.models.hazardous_chemicals import HazardousChemical
from app.models.user import User
from app.schemas.chemical_library import (
    ChemicalLibraryCollectRequest,
    ChemicalLibraryCreate,
    ChemicalLibraryUpdate,
)
from app.routers import chemical_library as router_mod


def _lib(**kw):
    defaults = dict(id="lib-1", name="乙醇", cas_no="67-56-1", created_at=datetime.now(), updated_at=datetime.now())
    defaults.update(kw)
    return ChemicalLibrary(**defaults)


def _admin():
    return User(id="u-admin", role="admin", email="a@x.com", name="A")


def _db(*results):
    db = AsyncMock()
    db.add = MagicMock()  # Session.add 为同步方法
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: results[0] if results else None)
    return db


@pytest.mark.asyncio
async def test_create_duplicate_cas_conflict():
    existing = _lib()
    db = _db(existing)
    body = ChemicalLibraryCreate(name="酒精", cas_no="67-56-1")
    with pytest.raises(HTTPException) as exc:
        await router_mod.create_library_item(body, _admin(), db)
    assert exc.value.status_code == 409
    assert "已存在" in exc.value.detail


@pytest.mark.asyncio
async def test_create_duplicate_name_when_no_cas():
    existing = _lib(id="lib-x", name="玻璃水", cas_no=None)
    db = _db(existing)
    body = ChemicalLibraryCreate(name="玻璃水", cas_no=None)
    with pytest.raises(HTTPException) as exc:
        await router_mod.create_library_item(body, _admin(), db)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_create_success():
    db = _db(None)

    async def _fake_refresh(obj):
        # 模拟真实 DB refresh：回填服务端生成的 id / 时间戳
        if obj.id is None:
            obj.id = "lib-new"
        if obj.created_at is None:
            obj.created_at = datetime.now()
        if obj.updated_at is None:
            obj.updated_at = datetime.now()

    db.refresh = AsyncMock(side_effect=_fake_refresh)
    body = ChemicalLibraryCreate(name="乙醇", cas_no="67-56-1", flash_point="12℃")
    resp = await router_mod.create_library_item(body, _admin(), db)
    assert resp.data.name == "乙醇"
    assert db.add.called and db.commit.await_count == 1


@pytest.mark.asyncio
async def test_create_with_alias_and_remark_passes_through():
    db = AsyncMock()
    db.add = MagicMock()  # Session.add 为同步方法
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)  # 无冲突

    async def _fake_refresh(obj):
        if obj.id is None:
            obj.id = "lib-alias-1"
        if obj.created_at is None:
            obj.created_at = datetime.now()
        if obj.updated_at is None:
            obj.updated_at = datetime.now()

    db.refresh = AsyncMock(side_effect=_fake_refresh)
    body = ChemicalLibraryCreate(name="甲醇", alias="木醇", cas_no="67-56-1", remark="剧毒")
    resp = await router_mod.create_library_item(body, _admin(), db)
    assert resp.data.name == "甲醇"
    assert resp.data.alias == "木醇"
    assert resp.data.remark == "剧毒"
    assert db.add.called and db.commit.await_count == 1


@pytest.mark.asyncio
async def test_update_rename_conflict_excludes_self():
    existing_other = _lib(id="lib-2", name="甲醇", cas_no="67-56-1")
    db = AsyncMock()
    db.get.return_value = _lib()  # 被编辑条目自身
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: existing_other)
    body = ChemicalLibraryUpdate(name="乙醇", cas_no="67-56-1")
    with pytest.raises(HTTPException) as exc:
        await router_mod.update_library_item("lib-1", body, _admin(), db)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_delete_missing_404():
    db = AsyncMock()
    db.get.return_value = None
    with pytest.raises(HTTPException) as exc:
        await router_mod.delete_library_item("nope", _admin(), db)
    assert exc.value.status_code == 404


def test_admin_endpoints_reject_normal_user():
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[get_current_user] = lambda: User(id="u1", role="user", email="u@x.com", name="U")
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    client = TestClient(app)
    r = client.post("/chemical-library", json={"name": "乙醇"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_collect_success_backfills_library_id():
    ent = Enterprise(id="ent-1", name="测试企业")
    chem = HazardousChemical(
        id="chem-1", enterprise_id="ent-1", name="次氯酸钠溶液",
        cas_no="7681-52-9", location="1#仓库", max_storage="2t",
    )
    db = AsyncMock()
    db.add = MagicMock()  # Session.add 为同步方法
    db.get.side_effect = lambda model, pk: {Enterprise: ent, HazardousChemical: chem}.get(model)
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)  # 无冲突

    async def _fake_refresh(obj):
        # 模拟真实 DB refresh：回填服务端生成的 id / 时间戳
        if obj.id is None:
            obj.id = "lib-collect-1"
        if obj.created_at is None:
            obj.created_at = datetime.now()
        if obj.updated_at is None:
            obj.updated_at = datetime.now()

    db.refresh = AsyncMock(side_effect=_fake_refresh)
    req = ChemicalLibraryCollectRequest(enterprise_id="ent-1", chemical_id="chem-1")
    resp = await router_mod.collect_from_enterprise(req, _admin(), db)
    assert resp.data.name == "次氯酸钠溶液"
    assert chem.library_id == resp.data.id
    assert db.commit.await_count == 1


@pytest.mark.asyncio
async def test_collect_missing_chemical_404():
    ent = Enterprise(id="ent-1", name="测试企业")
    db = AsyncMock()
    db.get.side_effect = lambda model, pk: ent if model is Enterprise else None
    req = ChemicalLibraryCollectRequest(enterprise_id="ent-1", chemical_id="missing")
    with pytest.raises(HTTPException) as exc:
        await router_mod.collect_from_enterprise(req, _admin(), db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_collect_cas_conflict_409():
    ent = Enterprise(id="ent-1", name="测试企业")
    chem = HazardousChemical(id="chem-1", enterprise_id="ent-1", name="乙醇", cas_no="67-56-1")
    db = AsyncMock()
    db.get.side_effect = lambda model, pk: {Enterprise: ent, HazardousChemical: chem}.get(model)
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: _lib())  # 已有同 CAS 条目
    req = ChemicalLibraryCollectRequest(enterprise_id="ent-1", chemical_id="chem-1")
    with pytest.raises(HTTPException) as exc:
        await router_mod.collect_from_enterprise(req, _admin(), db)
    assert exc.value.status_code == 409
