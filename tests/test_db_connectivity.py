"""Database connectivity test — verifies PostgreSQL is reachable."""

import pytest
from sqlalchemy import text

from borsel.db.session import async_session_factory


@pytest.mark.asyncio
async def test_database_connectivity() -> None:
    """Connect to PostgreSQL, execute SELECT 1, and confirm the result."""
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
