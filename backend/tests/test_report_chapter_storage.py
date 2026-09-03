from app.services.report_chapter_utils import (
    get_chapters,
    upsert_chapter,
    update_chapter_content,
)


def test_get_chapters_from_summary():
    assert get_chapters({"chapters": [{"key": "a", "content": "x"}]}) == [
        {"key": "a", "content": "x"},
    ]
    assert get_chapters({}) == []


def test_upsert_chapter_appends_and_updates():
    chapters = get_chapters({})
    chapters = upsert_chapter(chapters, "ch1", "标题", "内容A")
    chapters = upsert_chapter(chapters, "ch1", "标题", "内容B")
    chapters = upsert_chapter(chapters, "ch2", "标题2", "内容C")
    assert [c["key"] for c in chapters] == ["ch1", "ch2"]
    assert chapters[0]["content"] == "内容B"


def test_update_chapter_content_only_matches_key():
    chapters = [{"key": "a", "title": "A", "content": "1"}, {"key": "b", "title": "B", "content": "2"}]
    updated = update_chapter_content(chapters, "a", "new")
    assert updated[0]["content"] == "new"
    assert updated[1]["content"] == "2"
