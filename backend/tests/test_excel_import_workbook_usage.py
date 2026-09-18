"""Excel 导入守护：上传文件必须用 load_workbook 读，不能用 Workbook(...)（2026-09-18 修）。

踩过的坑：`resources_ext` 与 `risk_sources_ext` 的导入端点写成
`wb = Workbook(io.BytesIO(contents))`——openpyxl 的 `Workbook()` 第一个参数是 `write_only`，
于是它**新建了一个空白只写工作簿**、完全忽略上传内容，`wb.active` 为 None，
任何上传都会 500（`AttributeError: 'NoneType' object has no attribute 'iter_rows'`）。
结果是「资源导入」功能整体不可用（前端第一步下载模板修好后，第二步上传仍必崩）。
"""

from pathlib import Path

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"


def test_no_workbook_bytesio_misuse_in_routers():
    offenders = []
    for path in ROUTERS.glob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            code = line.split("#", 1)[0]  # 注释里提到这个写法不算违规
            if "Workbook(io.BytesIO" in code or "Workbook(BytesIO" in code:
                offenders.append(f"{path.name}:{lineno}")
    assert not offenders, f"这些文件仍在用 Workbook(BytesIO) 误读上传：{offenders}"


def test_import_endpoints_use_load_workbook_with_fallback():
    for name in ("resources_ext.py", "risk_sources_ext.py"):
        src = (ROUTERS / name).read_text(encoding="utf-8")
        assert "load_workbook(io.BytesIO(contents)" in src, name
        assert "导入文件格式无效" in src, f"{name} 缺损坏文件的 400 兜底"
