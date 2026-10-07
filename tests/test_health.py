from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.db.session import get_session
from src.main import app


def test_health() -> None:
    session = AsyncMock()
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)

    response = client.get("/api/health")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    session.execute.assert_awaited_once()
