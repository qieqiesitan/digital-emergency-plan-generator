"""法规源文件名净化（防目录穿越）——2026-09-18 审计修复。"""

import os

import pytest

from app.regulations import sync as reg_sync


@pytest.fixture()
def uploads_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(reg_sync, "UPLOADS_DIR", str(tmp_path / "uploads"))
    return tmp_path / "uploads"


def test_normal_filename_kept(uploads_tmp):
    path = reg_sync.save_source_file("reg1", b"data", "安全生产法.pdf")
    assert path.startswith(str(uploads_tmp))
    assert os.path.basename(path).endswith("_安全生产法.pdf")
    assert os.path.exists(path)


def test_traversal_filename_stays_inside(uploads_tmp):
    path = reg_sync.save_source_file("reg1", b"x", "../../evil.py")
    root = os.path.realpath(uploads_tmp)
    assert os.path.realpath(path).startswith(root + os.sep)
    assert "evil.py" in os.path.basename(path)
    assert not (uploads_tmp.parent / "evil.py").exists()


def test_absolute_and_backslash_filename_stays_inside(uploads_tmp):
    for name in ["/etc/passwd", "..\\..\\windows\\evil.txt", "....//x"]:
        path = reg_sync.save_source_file("reg1", b"x", name)
        root = os.path.realpath(uploads_tmp)
        assert os.path.realpath(path).startswith(root + os.sep), name
