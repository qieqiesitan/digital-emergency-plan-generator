"""报告草稿章节（summary.chapters）读写工具。"""
from typing import Any


def get_chapters(summary: dict | None) -> list[dict]:
    if not summary or not isinstance(summary.get("chapters"), list):
        return []
    return summary["chapters"]


def upsert_chapter(chapters: list[dict], key: str, title: str, content: str) -> list[dict]:
    for ch in chapters:
        if ch.get("key") == key:
            ch["title"] = title
            ch["content"] = content
            return chapters
    chapters.append({"key": key, "title": title, "content": content})
    return chapters


def update_chapter_content(chapters: list[dict], key: str, content: str) -> list[dict]:
    for ch in chapters:
        if ch.get("key") == key:
            ch["content"] = content
            return chapters
    return chapters


def chapters_to_summary(chapters: list[dict]) -> dict[str, Any]:
    return {"chapters": chapters}


def rebuild_chapters_summary(
    chapters: list[dict], prev_summary: dict | None = None
) -> dict[str, Any]:
    """用新章节重建 summary，同时保留既有扩展键（如图片 images），
    避免单章保存/重生成把 generate 阶段写入的四色图信息覆盖掉。"""
    summary = chapters_to_summary(chapters)
    if (
        prev_summary
        and isinstance(prev_summary, dict)
        and prev_summary.get("images")
    ):
        summary["images"] = prev_summary["images"]
    return summary
