import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.slskd import SlskdClient

@pytest.mark.asyncio
async def test_slskd_search_success():
    client = SlskdClient(api_url="http://mock-slskd/api/v0", api_key="test-key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "search-uuid-123", "searchText": "Daft Punk"}
        mock_post.return_value = mock_response

        res = await client.search("Daft Punk")
        assert res["id"] == "search-uuid-123"
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_slskd_get_search_responses():
    client = SlskdClient(api_url="http://mock-slskd/api/v0", api_key="test-key")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "username": "user1",
                "queueLength": 0,
                "files": [{"filename": "song.mp3", "size": 1000000}]
            }
        ]
        mock_get.return_value = mock_response

        res = await client.get_search_responses("search-uuid-123")
        assert len(res) == 1
        assert res[0]["username"] == "user1"
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_slskd_enqueue_download():
    client = SlskdClient(api_url="http://mock-slskd/api/v0", api_key="test-key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        success = await client.enqueue_download("user1", "song.mp3", 1000000)
        assert success is True
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_slskd_get_downloads():
    client = SlskdClient(api_url="http://mock-slskd/api/v0", api_key="test-key")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"filename": "song.mp3", "username": "user1", "state": "Downloading"}
        ]
        mock_get.return_value = mock_response

        res = await client.get_downloads()
        assert len(res) == 1
        assert res[0]["state"] == "Downloading"
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_slskd_cancel_download():
    client = SlskdClient(api_url="http://mock-slskd/api/v0", api_key="test-key")

    with patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response

        success = await client.cancel_download("user1", "transfer-id-123")
        assert success is True
        mock_delete.assert_called_once()
