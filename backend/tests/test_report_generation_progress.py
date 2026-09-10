"""全量生成逐章进度落库服务的单元测试。"""

import pytest

from app.services.report_generation_progress import save_generation_progress


class _FakeRow:
    def __init__(self, summary=None):
        self.id = "r1"
        self.summary = summary
        self.content = ""
        self.status = ""


class _FakeSession:
    def __init__(self, row):
        self.row = row
        self.committed = False
        self.closed = False

    async def get(self, model, report_id):
        return self.row

    async def commit(self):
        self.committed = True

    async def close(self):
        self.closed = True


def _factory(row):
    return lambda: _FakeSession(row)


@pytest.mark.asyncio
async def test_save_progress_writes_chapters_content_and_status():
    row = _FakeRow(summary={"overall_assessment": "x"})
    session = _FakeSession(row)
    ok = await save_generation_progress(
        type("M", (), {}),
        "r1",
        chapters=[{"key": "ch1", "title": "一", "content": "c1"}],
        content="# 正文",
        status="generating",
        session_factory=lambda: session,
    )
    assert ok is True
    assert session.committed is True
    assert session.closed is True
    assert row.summary == {
        "overall_assessment": "x",
        "chapters": [{"key": "ch1", "title": "一", "content": "c1"}],
    }
    assert row.content == "# 正文"
    assert row.status == "generating"


@pytest.mark.asyncio
async def test_save_progress_returns_false_when_report_missing():
    class MissingSession(_FakeSession):
        async def get(self, model, report_id):
            return None

    ok = await save_generation_progress(
        type("M", (), {}),
        "nope",
        chapters=[],
        session_factory=lambda: MissingSession(None),
    )
    assert ok is False
