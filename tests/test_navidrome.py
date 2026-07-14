import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.navidrome import NavidromeClient
from app.config import settings
import httpx

@pytest.mark.asyncio
async def test_navidrome_start_scan_success():
    client = NavidromeClient()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1",
                "scanStatus": {
                    "scanning": True,
                    "count": 12
                }
            }
        }
        mock_get.return_value = mock_response

        success = await client.start_scan()
        assert success is True
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_navidrome_search_track_duplicate_found():
    client = NavidromeClient()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "searchResult3": {
                    "song": [
                        {
                            "id": "song-1",
                            "title": "One More Time",
                            "artist": "Daft Punk",
                            "album": "Discovery"
                        }
                    ]
                }
            }
        }
        mock_get.return_value = mock_response

        found = await client.search_track("Daft Punk", "One More Time")
        assert found is True
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_navidrome_search_track_not_found():
    client = NavidromeClient()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "searchResult3": {
                    "song": []
                }
            }
        }
        mock_get.return_value = mock_response

        found = await client.search_track("Some Artist", "Unknown Song")
        assert found is False
        mock_get.assert_called_once()

def test_navidrome_auth_params_with_password():
    settings.NAVIDROME_PASSWORD = "testpassword123"
    settings.NAVIDROME_TOKEN = ""
    settings.NAVIDROME_SALT = ""

    client = NavidromeClient()
    params = client._get_auth_params()

    assert params["u"] == settings.NAVIDROME_USER
    assert "t" in params
    assert "s" in params
    assert params["v"] == "1.16.0"

@pytest.mark.asyncio
async def test_navidrome_ping_check_success():
    client = NavidromeClient()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1"
            }
        }
        mock_get.return_value = mock_resp

        res = await client.ping_check()
        assert res["connected"] is True
        assert res["version"] == "1.16.1"

@pytest.mark.asyncio
async def test_navidrome_ping_check_fail_connect():
    client = NavidromeClient()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        res = await client.ping_check()
        assert res["connected"] is False
        assert "Connection refused" in res["message"]

@pytest.mark.asyncio
async def test_navidrome_search_songs_by_artist():
    client = NavidromeClient()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "subsonic-response": {
                "status": "ok",
                "searchResult3": {
                    "song": [
                        {
                            "id": "song-1",
                            "title": "Humble",
                            "artist": "Kendrick Lamar",
                            "album": "Damn",
                            "coverArt": "cover-1"
                        }
                    ]
                }
            }
        }
        mock_get.return_value = mock_resp

        res = await client.search_songs_by_artist("Kendrick Lamar", "Humble")
        assert len(res) == 1
        assert res[0]["title"] == "Humble"
        assert res[0]["artist"] == "Kendrick Lamar"
