"""四色图临时预览的 TTL 回收（N-34：只涨不减会慢慢吃满磁盘）。"""
import os
import pathlib
import time

from app.services import floor_plan_storage_service as svc


def _mk_token_dir(root: pathlib.Path, token: str, age_hours: float) -> pathlib.Path:
    token_dir = root / token
    token_dir.mkdir(parents=True)
    source = token_dir / "source.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\n")
    stamp = time.time() - age_hours * 3600
    os.utime(source, (stamp, stamp))
    os.utime(token_dir, (stamp, stamp))
    return token_dir


def test_purge_removes_only_expired_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
    floor = tmp_path / "enterprises" / "ent1" / "floors" / "floor1" / svc.FOUR_COLOR_TMP
    floor.mkdir(parents=True)
    old = _mk_token_dir(floor, "a" * 32, age_hours=30)
    fresh = _mk_token_dir(floor, "b" * 32, age_hours=1)

    removed = svc.purge_four_color_temp(max_age_hours=24)

    assert removed == 1
    assert not old.exists(), "超过 24 小时的临时预览必须被回收"
    assert fresh.exists(), "未超期的临时预览不能误删（用户可能正在确认导入）"


def test_purge_removes_empty_root(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
    floor = tmp_path / "enterprises" / "ent1" / "floors" / "floor1" / svc.FOUR_COLOR_TMP
    floor.mkdir(parents=True)
    _mk_token_dir(floor, "c" * 32, age_hours=48)

    svc.purge_four_color_temp(max_age_hours=24)

    assert not floor.exists(), "清空后不应留下空壳目录"


def test_purge_is_noop_without_uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path / "not-exists")
    assert svc.purge_four_color_temp() == 0


def test_purge_disabled_when_max_age_non_positive(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "UPLOAD_DIR", tmp_path)
    floor = tmp_path / "enterprises" / "ent1" / "floors" / "floor1" / svc.FOUR_COLOR_TMP
    floor.mkdir(parents=True)
    old = _mk_token_dir(floor, "d" * 32, age_hours=999)
    assert svc.purge_four_color_temp(max_age_hours=0) == 0
    assert old.exists()


def test_maintenance_and_scheduler_call_purge():
    """源码守护：周期扫描与手动维护端点都要带上这段清理，否则等于没接。"""
    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    maintenance = (root / "routers" / "maintenance.py").read_text(encoding="utf-8")
    main_src = (root / "main.py").read_text(encoding="utf-8")
    assert "purge_four_color_temp()" in maintenance
    assert "purge_four_color_temp" in main_src
    assert "four_color_temp_purged" in maintenance
