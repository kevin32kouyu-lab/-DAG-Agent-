import os
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.agents.tools.tavily_tool import TavilySearchTool


def _run(coro):
    return asyncio.run(coro)


class TestTavilySearchTool:
    def test_no_api_key_returns_error(self):
        tool = TavilySearchTool()
        with patch.dict(os.environ, {}, clear=True):
            result = _run(tool.execute(query="test query"))
            assert "error" in result
            assert "TAVILY_API_KEY" in result["error"]

    def test_missing_query_returns_error(self):
        tool = TavilySearchTool()
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            result = _run(tool.execute())
            assert "error" in result
            assert "query" in result["error"]

    def test_successful_search(self):
        tool = TavilySearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"title": "Test Result", "url": "https://example.com",
                 "content": "This is a test", "score": 0.9},
            ],
            "answer": "Summary answer",
        }

        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                result = _run(tool.execute(
                    query="test query", search_depth="basic", max_results=5
                ))
                assert result["query"] == "test query"
                assert result["total_results"] == 1
                assert result["results"][0]["title"] == "Test Result"
                assert result["results"][0]["url"] == "https://example.com"
                assert result["answer"] == "Summary answer"

    def test_401_returns_error(self):
        tool = TavilySearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.dict(os.environ, {"TAVILY_API_KEY": "invalid-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                result = _run(tool.execute(query="test"))
                assert "error" in result
                assert "无效" in result["error"]

    def test_429_quota_exceeded(self):
        tool = TavilySearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                result = _run(tool.execute(query="test"))
                assert "error" in result
                assert "配额" in result["error"]

    def test_advanced_search_depth(self):
        tool = TavilySearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "answer": ""}

        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                _run(tool.execute(query="test", search_depth="advanced"))
                call_args = mock_post.call_args
                payload = call_args.kwargs["json"]
                assert payload["search_depth"] == "advanced"

    def test_max_results_clamped_to_20(self):
        tool = TavilySearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "answer": ""}

        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                _run(tool.execute(query="test", max_results=100))
                call_args = mock_post.call_args
                payload = call_args.kwargs["json"]
                assert payload["max_results"] == 20
