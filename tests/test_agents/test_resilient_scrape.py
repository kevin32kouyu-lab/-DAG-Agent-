import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os
from src.agents.tools.web_tools import WebScrapeTool


@pytest.mark.asyncio
async def test_resilient_scrape_line_1_success():
    """Verify that if direct scrape succeeds, it is returned directly."""
    mock_html = "<html><head><title>Direct Success</title></head><body><p>This is direct scrape body text with long content.</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.text = mock_html
    mock_resp.status_code = 200
    
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)) as mock_get:
        tool = WebScrapeTool()
        res = await tool.execute(url="https://example.com/direct")
        
        assert res["source"] == "direct"
        assert res["title"] == "Direct Success"
        assert "direct scrape body" in res["text"]
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_resilient_scrape_fallback_to_tavily():
    """Verify that if direct scrape fails, it falls back to Tavily extract."""
    # Line 1 fails with 403
    mock_resp_403 = MagicMock()
    mock_resp_403.status_code = 403
    
    # Line 2 Tavily succeeds
    mock_tavily_resp = MagicMock()
    mock_tavily_resp.status_code = 200
    mock_tavily_resp.json = MagicMock(return_value={
        "results": [{
            "url": "https://example.com/tavily",
            "title": "Tavily Extracted Title",
            "raw_content": "This is content extracted by Tavily extract API.",
            "error": None
        }]
    })
    
    with patch.dict(os.environ, {"TAVILY_API_KEY": "test_key"}):
        async def mock_post(url, *args, **kwargs):
            if url == "https://api.tavily.com/extract":
                return mock_tavily_resp
            raise ValueError(f"Unexpected url {url}")
            
        async def mock_get(url, *args, **kwargs):
            return mock_resp_403

        with patch("httpx.AsyncClient.get", AsyncMock(side_effect=mock_get)), \
             patch("httpx.AsyncClient.post", AsyncMock(side_effect=mock_post)):
             
            tool = WebScrapeTool()
            res = await tool.execute(url="https://example.com/tavily")
            
            assert res["source"] == "tavily_extract"
            assert res["title"] == "Tavily Extracted Title"
            assert "Tavily extract API" in res["text"]


@pytest.mark.asyncio
async def test_resilient_scrape_fallback_to_wayback():
    """Verify that if direct scrape and Tavily scrape both fail, it falls back to Wayback snapshots."""
    # Line 1 fails
    mock_resp_503 = MagicMock()
    mock_resp_503.status_code = 503
    
    # Line 2 Tavily fails
    mock_tavily_fail = MagicMock()
    mock_tavily_fail.status_code = 500
    
    # Line 3 Wayback availability succeeds
    mock_avail_resp = MagicMock()
    mock_avail_resp.status_code = 200
    mock_avail_resp.json = MagicMock(return_value={
        "archived_snapshots": {
            "closest": {
                "available": True,
                "url": "http://web.archive.org/web/20260101000000/https://example.com/wayback",
                "timestamp": "20260101000000"
            }
        }
    })
    
    # Snapshot retrieval succeeds
    mock_snap_resp = MagicMock()
    mock_snap_resp.status_code = 200
    mock_snap_resp.text = "<html><head><title>Wayback Snapshot</title></head><body><p>This is wayback historical data.</p></body></html>"

    with patch.dict(os.environ, {"TAVILY_API_KEY": "test_key"}):
        async def mock_get(url, *args, **kwargs):
            if "wayback/available" in str(url):
                return mock_avail_resp
            if "web.archive.org" in str(url):
                return mock_snap_resp
            return mock_resp_503
            
        async def mock_post(url, *args, **kwargs):
            return mock_tavily_fail

        with patch("httpx.AsyncClient.get", AsyncMock(side_effect=mock_get)), \
             patch("httpx.AsyncClient.post", AsyncMock(side_effect=mock_post)):
             
            tool = WebScrapeTool()
            res = await tool.execute(url="https://example.com/wayback")
            
            assert res["source"] == "wayback_snapshot"
            assert res["title"] == "Wayback Snapshot"
            assert "historical data" in res["text"]
            assert res["snapshot_url"] == "http://web.archive.org/web/20260101000000/https://example.com/wayback"


@pytest.mark.asyncio
async def test_resilient_scrape_all_fail():
    """Verify that if all 3 tiers fail, an error dictionary is returned gracefully."""
    mock_resp_fail = MagicMock()
    mock_resp_fail.status_code = 404
    
    with patch.dict(os.environ, {"TAVILY_API_KEY": ""}):
        with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp_fail)):
            tool = WebScrapeTool()
            res = await tool.execute(url="https://example.com/all_fail")
            
            assert "error" in res
            assert "Failed to scrape URL through all 3 defense lines" in res["error"]


@pytest.mark.asyncio
async def test_resilient_scrape_logs_tavily_fallback_exception(caplog):
    """Tavily 兜底异常应可见，但不阻塞后续 Wayback 兜底。"""
    mock_resp_503 = MagicMock()
    mock_resp_503.status_code = 503
    mock_wayback_empty = MagicMock()
    mock_wayback_empty.status_code = 200
    mock_wayback_empty.json = MagicMock(return_value={"archived_snapshots": {}})

    async def mock_get(url, *args, **kwargs):
        if "wayback/available" in str(url):
            return mock_wayback_empty
        return mock_resp_503

    async def mock_post(*_args, **_kwargs):
        raise RuntimeError("tavily unavailable")

    caplog.set_level("WARNING", logger="src.agents.tools.web_tools")

    with patch.dict(os.environ, {"TAVILY_API_KEY": "test_key"}):
        with patch("httpx.AsyncClient.get", AsyncMock(side_effect=mock_get)), \
             patch("httpx.AsyncClient.post", AsyncMock(side_effect=mock_post)):
            tool = WebScrapeTool()
            res = await tool.execute(url="https://example.com/tavily_error")

    assert "error" in res
    assert "Tavily 兜底抓取失败" in caplog.text
    assert "tavily unavailable" in caplog.text


@pytest.mark.asyncio
async def test_resilient_scrape_logs_wayback_fallback_exception(caplog):
    """Wayback 兜底异常应可见，同时保持错误返回。"""
    async def mock_get(*_args, **_kwargs):
        raise RuntimeError("wayback unavailable")

    caplog.set_level("WARNING", logger="src.agents.tools.web_tools")

    with patch.dict(os.environ, {"TAVILY_API_KEY": ""}):
        with patch("httpx.AsyncClient.get", AsyncMock(side_effect=mock_get)):
            tool = WebScrapeTool()
            res = await tool.execute(url="https://example.com/wayback_error")

    assert "error" in res
    assert "Wayback 兜底抓取失败" in caplog.text
    assert "wayback unavailable" in caplog.text
