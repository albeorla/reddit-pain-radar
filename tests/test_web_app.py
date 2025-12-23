import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from pain_radar.web_app import app

client = TestClient(app)

def test_read_root():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Public Pain Archive" in response.text

@pytest.mark.asyncio
async def test_create_alert(tmp_path):
    """Test creating an alert."""
    db_file = tmp_path / "test.db"
    
    # Mock settings to use temp DB
    with patch("pain_radar.web_app.settings") as mock_settings:
        mock_settings.db_path = str(db_file)
        
        # We need the table to exist
        from pain_radar.store import AsyncStore
        store = AsyncStore(str(db_file))
        await store.connect()
        await store.init_db()
        await store.close()
        
        response = client.post(
            "/alerts",
            data={"email": "test@example.com", "keyword": "test"}
        )
        
        assert response.status_code == 200
        assert "Subscribed!" in response.text
        
        # Verify in DB
        store = AsyncStore(str(db_file))
        await store.connect()
        async with store.connection() as conn:
            cursor = await conn.execute("SELECT * FROM alerts WHERE email = ?", ("test@example.com",))
            row = await cursor.fetchone()
            assert row is not None
            assert row["keyword"] == "test"
        await store.close()

@pytest.mark.asyncio
async def test_read_latest_archive_empty(tmp_path):
    """Test reading archive with no data."""
    db_file = tmp_path / "test.db"
    
    with patch("pain_radar.web_app.settings") as mock_settings:
        mock_settings.db_path = str(db_file)
        
        from pain_radar.store import AsyncStore
        store = AsyncStore(str(db_file))
        await store.connect()
        await store.init_db()
        await store.close()
        
        response = client.get("/archive/latest")
        
        assert response.status_code == 200
        assert "No reports found yet" in response.text
