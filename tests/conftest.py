"""Shared test fixtures."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from workflowtwin.core.config import Settings
from workflowtwin.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    """Run async endpoint tests on the application's asyncio backend."""
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Create an API client with deterministic test configuration."""
    settings = Settings(
        _env_file=None,
        environment="test",
        log_level="ERROR",
        service_name="workflowtwin-api-test",
    )
    transport = ASGITransport(app=create_app(settings))
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
