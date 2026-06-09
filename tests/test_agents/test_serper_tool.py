"""Tests for SerperSearchTool."""
import os
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.tools.serper_tool import SerperSearchTool


def _run(coro):
    return asyncio.run(coro)


class TestSerperSearchTool:
    def test_no_api_key_returns_error(self):
        tool = SerperSearchTool()
        with patch.dict(os.environ, {}, clear=True):
            result = _run(tool.execute(query="test query"))
            assert "error" in result
            assert "SERPER_API_KEY" in result["error"]

    def test_missing_query_returns_error(self):
        tool = SerperSearchTool()
        with patch.dict(os.environ, {"SERPER_API_KEY": "test-key"}):
            result = _run(tool.execute())
            assert "error" in result
            assert "query" in result["error"]

    def test_successful_search(self):
        tool = SerperSearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic": [
                {
                    "title": "Linear - The system for product development",
                    "link": "https://linear.app/",
                    "snippet": "Linear is a product development system.",
                    "position": 1,
                },
                {
                    "title": "Linear Pricing",
                    "link": "https://linear.app/pricing",
                    "snippet": "Free plan available.",
                    "position": 2,
                    "sitelinks": [
                        {"title": "Features", "link": "https://linear.app/features"},
                    ],
                },
            ],
            "answerBox": {"answer": "Linear is a project management tool"},
        }

        with patch.dict(os.environ, {"SERPER_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                result = _run(tool.execute(query="Linear project management"))

                assert result["query"] == "Linear project management"
                assert result["total_results"] == 2
                assert result["results"][0]["title"] == "Linear - The system for product development"
                assert result["results"][0]["url"] == "https://linear.app/"
                assert result["results"][1]["sitelinks"][0]["title"] == "Features"
                assert result["answerBox"]["answer"] == "Linear is a project management tool"

    def test_default_params(self):
        tool = SerperSearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"organic": []}

        with patch.dict(os.environ, {"SERPER_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                _run(tool.execute(query="test"))

                call_args = mock_post.call_args
                payload = call_args.kwargs["json"]
                assert payload["gl"] == "cn"
                assert payload["hl"] == "zh-cn"
                assert payload["num"] == 10

    def test_custom_params(self):
        tool = SerperSearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"organic": []}

        with patch.dict(os.environ, {"SERPER_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                _run(tool.execute(query="Notion", gl="us", hl="en", num=5))

                call_args = mock_post.call_args
                payload = call_args.kwargs["json"]
                assert payload["gl"] == "us"
                assert payload["hl"] == "en"
                assert payload["num"] == 5

    def test_num_clamped_to_20(self):
        tool = SerperSearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"organic": []}

        with patch.dict(os.environ, {"SERPER_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                _run(tool.execute(query="test", num=100))

                call_args = mock_post.call_args
                payload = call_args.kwargs["json"]
                assert payload["num"] == 20

    def test_401_returns_error(self):
        tool = SerperSearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.dict(os.environ, {"SERPER_API_KEY": "invalid-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                result = _run(tool.execute(query="test"))
                assert "error" in result
                assert "invalid" in result["error"].lower()

    def test_429_returns_error(self):
        tool = SerperSearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch.dict(os.environ, {"SERPER_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                result = _run(tool.execute(query="test"))
                assert "error" in result
                assert "rate limit" in result["error"].lower()

    def test_402_quota_exhausted(self):
        tool = SerperSearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 402

        with patch.dict(os.environ, {"SERPER_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                result = _run(tool.execute(query="test"))
                assert "error" in result
                assert "quota" in result["error"].lower()

    def test_news_search_type(self):
        tool = SerperSearchTool()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "news": [
                {
                    "title": "Linear raises $35M",
                    "link": "https://techcrunch.com/linear",
                    "snippet": "Linear raises Series B.",
                    "source": "TechCrunch",
                    "date": "2024-01-15",
                },
            ],
        }

        with patch.dict(os.environ, {"SERPER_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                result = _run(tool.execute(query="Linear funding", type="news"))

                assert result["search_type"] == "news"
                assert result["results"][0]["source"] == "TechCrunch"
                assert result["results"][0]["date"] == "2024-01-15"

                # Verify correct endpoint was called
                call_args = mock_post.call_args
                assert "/news" in str(call_args)

    def test_timeout_returns_error(self):
        import httpx

        tool = SerperSearchTool()
        with patch.dict(os.environ, {"SERPER_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = httpx.TimeoutException("timed out")
                result = _run(tool.execute(query="test"))
                assert "error" in result
                assert "timed out" in result["error"].lower()

    def test_snippet_truncated_to_500_chars(self):
        tool = SerperSearchTool()
        long_snippet = "x" * 1000
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic": [
                {"title": "Test", "link": "https://example.com", "snippet": long_snippet, "position": 1},
            ],
        }

        with patch.dict(os.environ, {"SERPER_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                result = _run(tool.execute(query="test"))
                assert len(result["results"][0]["snippet"]) == 500
