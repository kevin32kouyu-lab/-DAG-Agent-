import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.agents.tools.web_tools import WebScrapeTool, WebSearchTool


def test_web_scrape_tool_schema():
    tool = WebScrapeTool()
    assert tool.name == "web_scrape"
    assert "url" in tool.param_schema


def test_web_search_tool_schema():
    tool = WebSearchTool()
    assert tool.name == "web_search"
    assert "query" in tool.param_schema


@pytest.mark.asyncio
async def test_web_scrape_returns_content():
    mock_html = "<html><head><title>Test Page</title></head><body><h1>Test Page</h1><p>Content</p></body></html>"
    mock_response = MagicMock()
    mock_response.text = mock_html
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_response)):
        tool = WebScrapeTool()
        result = await tool.execute(url="https://example.com")
        assert "title" in result
        assert result["title"] == "Test Page"
        assert "Content" in result["text"]


@pytest.mark.asyncio
async def test_web_scrape_extracts_key_paragraphs():
    mock_html = "<html><body><p>First paragraph with enough content to be considered a key paragraph here.</p><p>Short.</p><p>Third paragraph with enough content here as well for extraction.</p></body></html>"
    mock_response = MagicMock()
    mock_response.text = mock_html
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_response)):
        tool = WebScrapeTool()
        result = await tool.execute(url="https://example.com")
        assert len(result["key_paragraphs"]) == 2
