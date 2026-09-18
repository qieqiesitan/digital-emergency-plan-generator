"""删除法规时清理磁盘残留（2026-09-18 补）。

DELETE 此前只删图谱节点 + 向量索引，`data/texts/{id}.md` 与 `data/uploads/{id}/` 下的
源文件会一直留着；反复"入库→删除"就积累孤儿文件（图谱节点没了，文件也没人引用）。
"""

from app.regulations import sync


def test_remove_regulation_files_cleans_texts_and_sources(tmp_path, monkeypatch):
    texts = tmp_path / "texts"
    uploads = tmp_path / "uploads"
    texts.mkdir()
    (uploads / "reg_probe").mkdir(parents=True)
    (texts / "reg_probe.md").write_text("# 探针法规\n", encoding="utf-8")
    (uploads / "reg_probe" / "20260918_src.pdf").write_bytes(b"%PDF-1.4 probe")
    (texts / "reg_keep.md").write_text("# 要保留的\n", encoding="utf-8")

    monkeypatch.setattr(sync, "TEXTS_DIR", str(texts))
    monkeypatch.setattr(sync, "UPLOADS_DIR", str(uploads))

    removed = sync.remove_regulation_files("reg_probe")
    assert removed == {"texts": 1, "sources": 1}
    assert not (texts / "reg_probe.md").exists()
    assert not (uploads / "reg_probe").exists()          # 目录已空 → 一并删除
    assert (texts / "reg_keep.md").exists()              # 不误删其它法规


def test_remove_regulation_files_is_noop_for_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "TEXTS_DIR", str(tmp_path / "texts"))
    monkeypatch.setattr(sync, "UPLOADS_DIR", str(tmp_path / "uploads"))
    assert sync.remove_regulation_files("nope") == {"texts": 0, "sources": 0}
