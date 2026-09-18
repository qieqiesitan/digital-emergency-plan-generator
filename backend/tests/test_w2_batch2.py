"""W2 批次二：调度器单实例、权限种子、存储型 XSS 防护（回归守护）。"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import hazard_scheduler

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent


# ── 1. APScheduler 单实例（advisory lock 选主） ──

def _session(locked: bool):
    session = MagicMock()
    result = MagicMock()
    result.scalar.return_value = locked
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_hazard_scan_skips_when_lock_not_acquired(monkeypatch):
    called = AsyncMock()
    monkeypatch.setattr(hazard_scheduler, "run_hazard_scans", called)
    out = await hazard_scheduler.run_hazard_scans_leader_only(_session(False))
    assert out is None
    called.assert_not_awaited()


@pytest.mark.asyncio
async def test_hazard_scan_runs_and_unlocks_when_lock_acquired(monkeypatch):
    called = AsyncMock(return_value={"generated": 0})
    monkeypatch.setattr(hazard_scheduler, "run_hazard_scans", called)
    session = _session(True)
    out = await hazard_scheduler.run_hazard_scans_leader_only(session)
    assert out == {"generated": 0}
    called.assert_awaited_once()
    assert session.execute.await_count == 2, "必须加锁 + 解锁各一次"


# ── 2. 权限种子迁移 ──

def test_menu_seed_migration_covers_known_gaps():
    sql = (BACKEND / "db_migration_20260918_menu_seed_fix.sql").read_text(encoding="utf-8")
    assert "menu:regulations" in sql, "全新安装缺 menu:regulations"
    assert "menu:enterprises" in sql, "普通用户缺企业管理菜单"
    assert "r.code = 'user'" in sql and "menu:ai_config" in sql, "AI 配置菜单应按后端鉴权收口"
    assert "ON CONFLICT" in sql


# ── 3. 存储型 XSS：所有 dangerouslySetInnerHTML 必须先消毒 ──

def test_all_dangerous_html_sites_are_sanitized():
    src_root = REPO / "frontend" / "src"
    offenders = []
    for path in src_root.rglob("*.tsx"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "dangerouslySetInnerHTML" in line and "sanitize" not in line:
                offenders.append(f"{path.relative_to(REPO)}:{lineno}")
    assert not offenders, f"存在未消毒的 dangerouslySetInnerHTML：{offenders}"


def test_mermaid_no_longer_uses_loose_security():
    src = (REPO / "frontend" / "src" / "components" / "plan" / "MermaidRenderer.tsx").read_text(encoding="utf-8")
    assert 'securityLevel: "loose"' not in src
    assert 'securityLevel: "strict"' in src
    assert "sanitizeSvg" in src


def test_shared_sanitize_helper_exists():
    src = (REPO / "frontend" / "src" / "utils" / "sanitize.ts").read_text(encoding="utf-8")
    assert "DOMPurify" in src and "sanitizeHtml" in src and "sanitizeSvg" in src
