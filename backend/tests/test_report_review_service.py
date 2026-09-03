from app.services.report_review_service import review_report_chapters


def test_short_chapter_reported():
    issues = review_report_chapters([{"key": "ch1", "title": "一、辨识", "content": "太短"}])
    assert any(i["section_key"] == "ch1" and i["severity"] == "error" for i in issues)


def test_markdown_table_and_mermaid_reported():
    content = "正文\n| a | b |\n| --- | --- |\n```mermaid\nflowchart TD\n```"
    issues = review_report_chapters([{"key": "ch2", "title": "二、汇总", "content": content}])
    kinds = {i["kind"] for i in issues}
    assert "markdown_table" in kinds
    assert "mermaid_block" in kinds


def test_placeholder_reported():
    issues = review_report_chapters([{"key": "ch3", "title": "三、评估", "content": "内容含 XXX 与 xxx" * 5}])
    assert any(i["kind"] == "placeholder" for i in issues)


def test_clean_chapter_no_issues():
    issues = review_report_chapters([{"key": "ch4", "title": "四、措施", "content": "（内容完整）" * 60}])
    assert issues == []
