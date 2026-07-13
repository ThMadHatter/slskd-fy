import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import DownloadHistory
from app.services.duplicate_detector import check_duplicate

# Setup in-memory test database
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(bind=engine)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.mark.asyncio
async def test_check_duplicate_not_found():
    db = TestingSessionLocal()

    with patch("app.services.navidrome.NavidromeClient.search_track", new_callable=AsyncMock) as mock_nd:
        mock_nd.return_value = False

        res = await check_duplicate(db, "Daft Punk", "Get Lucky")
        assert res["is_duplicate"] is False
        assert len(res["sources"]) == 0

    db.close()

@pytest.mark.asyncio
async def test_check_duplicate_found_navidrome():
    db = TestingSessionLocal()

    with patch("app.services.navidrome.NavidromeClient.search_track", new_callable=AsyncMock) as mock_nd:
        mock_nd.return_value = True

        res = await check_duplicate(db, "Daft Punk", "Get Lucky")
        assert res["is_duplicate"] is True
        assert "Navidrome Library" in res["sources"]

    db.close()

@pytest.mark.asyncio
async def test_check_duplicate_found_history():
    db = TestingSessionLocal()

    # Add dummy download history entry with completed status
    entry = DownloadHistory(
        search_query="Daft Punk", artist="Daft Punk", track="Get Lucky", album="RAM",
        filename="song.mp3", source_user="user1", format="mp3", status="completed"
    )
    db.add(entry)
    db.commit()

    with patch("app.services.navidrome.NavidromeClient.search_track", new_callable=AsyncMock) as mock_nd:
        mock_nd.return_value = False

        res = await check_duplicate(db, "Daft Punk", "Get Lucky")
        assert res["is_duplicate"] is True
        assert "Download History (Artist/Title)" in res["sources"]

    db.close()
