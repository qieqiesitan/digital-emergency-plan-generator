import asyncio
from unittest.mock import AsyncMock, Mock

from app.services.risk_stats_service import count_enterprise_risk_events


def test_count_enterprise_risk_events_returns_count():
    db = AsyncMock()
    result = Mock()
    result.scalar.return_value = 7
    db.execute.return_value = result

    count = asyncio.run(count_enterprise_risk_events(db, "ent-1"))

    assert count == 7
