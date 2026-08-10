# Codex Custom Subagents task handoff v1

Task: task_b21_fix

## 任务：修复 B2-1 文件解析 4 项重要问题（编码/错误语义/句柄/测试）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 c3b99c8。启动时 `cd` 到该目录，git status 确认干净。

### 问题 1（重要）：CSV 编码兼容（GBK/UTF-8 BOM）

`backend/app/services/file_parser.py` 的 `_parse_csv`：优先 `utf-8-sig` 解码，失败 fallback 到 `gbk`，再失败 `utf-8 errors=ignore`：

```python
def _parse_csv(data: bytes) -> str:
    raw = None
    for enc in ("utf-8-sig", "gbk"):
        try:
            raw = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        raw = data.decode("utf-8", errors="ignore")
    rows = list(csv.reader(io.StringIO(raw)))
    return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows if any(cell.strip() for cell in row))
```

### 问题 2（重要）：损坏/空文件错误语义统一

在 `parse_file_text` 内对每种格式的解析包 try/except，将解析异常统一转为 `ValueError("文件解析失败，请确认文件未损坏且格式正确")`（保留原始异常上下文 `from e`）。格式不支持仍走原 ValueError。

### 问题 3（重要）：显式关闭文件句柄

`_parse_xlsx`：`try/finally` 中 `wb.close()`；`_parse_pdf`：`try/finally` 中 `doc.close()`。

### 问题 4（重要）：补 docx/pdf/损坏文件测试

`backend/tests/test_file_parser.py` 追加：

- `test_parse_docx_bytes`：用 python-docx 构造内存 docx（含一段中文 + 一个表格），断言文本包含段落与表格内容。
- `test_parse_pdf_bytes`：若环境有 PyMuPDF 则构造内存 PDF（fitz.open(stream=...) 写一页文本），断言文本包含；若无 fitz 则 `pytest.skip`。
- `test_parse_corrupt_xlsx_raises_valueerror`：`parse_file_text("a.xlsx", b"not a zip")` 抛 ValueError（统一错误语义）。
- `test_parse_csv_gbk`：GBK 编码的 CSV 字节（`"名称,cas\n甲醇,67-56-1".encode("gbk")`）断言正确解码出中文。

### 步骤 5：测试验证 + Commit

运行：`cd backend && python -m pytest tests/test_file_parser.py -v`

再全量：`python -m pytest tests/ -q`（与基线一致，无新增失败）。

```bash
git add backend/app/services/file_parser.py backend/tests/test_file_parser.py
git commit -m "fix(import): robust csv encoding, unified parse errors, close handles, add format tests"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 按步骤实现
2. 测试验证
3. 提交
4. 自审：GBK/BOM 中文解码正确？损坏文件统一 ValueError？句柄关闭？docx/pdf 测试有效（fitz 缺失时 skip）？
5. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、测试结果、提交 SHA、自审发现
