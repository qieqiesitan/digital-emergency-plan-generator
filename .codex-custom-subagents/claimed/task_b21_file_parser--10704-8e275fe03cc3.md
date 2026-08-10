# Codex Custom Subagents task handoff v1

Task: task_b21_file_parser

## 任务：文件解析工具（易用性优化计划 B2 任务 B2-1）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成 TDD 实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含计划 B 提交（289111a）。启动时 `cd` 到该目录，git status 确认干净。

### 步骤 1：编写失败测试

新建 `backend/tests/test_file_parser.py`：

```python
import io

import pytest

from app.services.file_parser import parse_file_text


def test_parse_csv_text():
    text = parse_file_text("chem.csv", b"name,cas\nmethanol,67-56-1\nethanol,64-17-5\n")
    assert "methanol" in text
    assert "67-56-1" in text


def test_parse_plain_text_txt():
    text = parse_file_text("note.txt", "企业地址：杭州市XX区".encode("utf-8"))
    assert "企业地址" in text


def test_parse_unsupported_extension_raises():
    with pytest.raises(ValueError):
        parse_file_text("file.exe", b"x")


def test_parse_xlsx_bytes():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["化学品名称", "CAS号"])
    ws.append(["甲醇", "67-56-1"])
    buf = io.BytesIO()
    wb.save(buf)
    text = parse_file_text("chem.xlsx", buf.getvalue())
    assert "甲醇" in text
    assert "67-56-1" in text
```

运行确认失败：`cd backend && python -m pytest tests/test_file_parser.py -v`（预期 ModuleNotFoundError）。

### 步骤 2：实现解析工具

新建 `backend/app/services/file_parser.py`：

```python
"""导入文件解析：xlsx / csv / docx / pdf / txt → 纯文本。"""
import csv
import io


def parse_file_text(filename: str, data: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "csv":
        return _parse_csv(data)
    if ext == "xlsx":
        return _parse_xlsx(data)
    if ext == "docx":
        return _parse_docx(data)
    if ext == "pdf":
        return _parse_pdf(data)
    if ext in ("txt", "md"):
        return data.decode("utf-8", errors="ignore")
    raise ValueError(f"不支持的文件格式：.{ext}，支持 xlsx/csv/docx/pdf/txt")


def _parse_csv(data: bytes) -> str:
    text = data.decode("utf-8", errors="ignore")
    rows = list(csv.reader(io.StringIO(text)))
    return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows if any(cell.strip() for cell in row))


def _parse_xlsx(data: bytes) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    parts = []
    for ws in wb.worksheets:
        parts.append(f"【工作表：{ws.title}】")
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _parse_docx(data: bytes) -> str:
    import docx
    doc = docx.Document(io.BytesIO(data))
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _parse_pdf(data: bytes) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(stream=data, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)
```

（依赖已存在：openpyxl / python-docx / PyMuPDF 均在 requirements.txt。）

### 步骤 3：运行测试验证通过

运行：`cd backend && python -m pytest tests/test_file_parser.py -v`

预期：4 个测试 PASS。

### 步骤 4：全量后端测试 + Commit

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS（与基线一致）。

```bash
git add backend/app/services/file_parser.py backend/tests/test_file_parser.py
git commit -m "feat(import): file parser for xlsx/csv/docx/pdf/txt"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 严格按任务描述 TDD 实现
2. 运行测试验证（步骤 3/4）
3. 提交（步骤 4）
4. 自审：四种格式 + txt 都覆盖？不支持格式明确报错？无多余依赖？
5. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、测试结果、提交 SHA、自审发现
