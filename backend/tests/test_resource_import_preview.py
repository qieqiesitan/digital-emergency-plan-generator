"""资源导入预览：示例行跳过 + 有效/错误统计（2026-09-18 修）。

这个端点此前**零测试**，因此两个真缺陷一直没被发现：
①`Workbook(io.BytesIO(...))` 误用导致任何上传都 500（见 test_excel_import_workbook_usage.py）；
②模板自带示例行会被前端"下一步"整批落库，把示例数据导进真实台账。
"""

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.dependencies import get_current_user
from app.routers import resources_ext
from app.database import get_db


def _xlsx_bytes(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["类别", "名称", "规格型号", "数量", "单位", "存放位置", "责任人",
               "联系电话", "是否外部", "外部地址", "距离(公里)"])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture()
def client(monkeypatch):
    app = FastAPI()
    app.include_router(resources_ext.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "u1"})()
    app.dependency_overrides[get_db] = lambda: None

    async def _noop(enterprise_id, user_id, db):
        return {}

    monkeypatch.setattr(resources_ext, "_get_enterprise_data", _noop)
    return TestClient(app)


def _post(client, rows):
    return client.post(
        "/api/v1/enterprises/e1/resources/import",
        files={"file": ("import.xlsx", _xlsx_bytes(rows),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def test_preview_skips_example_and_reports_counts(client):
    rows = [
        ["消防设施", "【示例】干粉灭火器", "MFZ/ABC8", 20, "个", "示例位置", "示例-张三",
         "13800001111", "否", "", ""],
        ["消防设施", "探针灭火器", "MFZ/ABC4", 12, "具", "一号库房", "王主管",
         "13800000000", "否", "", ""],
        ["不存在的类别", "坏行资源", "", 1, "件", "", "", "", "否", "", ""],
    ]
    resp = _post(client, rows)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["valid_count"] == 1
    assert data["error_count"] == 1
    assert data["skipped_examples"] == 1
    names = [i["data"]["name"] for i in data["items"]]
    # 错误行也会出现在 items 里（供页面标红提示），但示例行必须被完全跳过
    assert names == ["探针灭火器", "坏行资源"], names
    assert all("【示例】" not in n for n in names)
    err = next(i for i in data["items"] if i["errors"])
    assert "无效类别" in err["errors"][0]


def test_broken_file_returns_400_not_500(client):
    resp = client.post(
        "/api/v1/enterprises/e1/resources/import",
        files={"file": ("broken.xlsx", b"not-an-xlsx", "application/vnd.ms-excel")},
    )
    assert resp.status_code == 400
    assert "格式无效" in resp.json()["detail"]
