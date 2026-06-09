"""Tests for npm, pypi, and yfinance tools — all free, no API keys needed."""

import pytest
from src.agents.tools.npm_tool import NpmTool
from src.agents.tools.pypi_tool import PyPITool
from src.agents.tools.yfinance_tool import YFinanceTool


# ── npm ──

@pytest.mark.asyncio
async def test_npm_package_info():
    tool = NpmTool()
    result = await tool.execute(action="info", package="express")
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["name"].lower() == "express"
    assert result["latest_version"]
    assert result["license"]


@pytest.mark.asyncio
async def test_npm_search():
    tool = NpmTool()
    result = await tool.execute(action="search", query="express", limit=5)
    if "error" in result and "connect" in result["error"].lower():
        pytest.skip("npm registry unreachable (network/proxy issue)")
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["total"] > 0
    assert len(result["results"]) > 0
    assert result["results"][0]["name"]


@pytest.mark.asyncio
async def test_npm_downloads():
    tool = NpmTool()
    result = await tool.execute(action="downloads", package="express", period="last-week")
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["downloads"] >= 0
    assert result["period"] == "last-week"


@pytest.mark.asyncio
async def test_npm_versions():
    tool = NpmTool()
    result = await tool.execute(action="versions", package="express", limit=5)
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["total_versions"] > 0
    assert len(result["versions"]) > 0
    assert result["versions"][0]["version"]


@pytest.mark.asyncio
async def test_npm_not_found():
    tool = NpmTool()
    result = await tool.execute(action="info", package="this-package-definitely-does-not-exist-xyz123")
    assert "error" in result


# ── PyPI ──

@pytest.mark.asyncio
async def test_pypi_package_info():
    tool = PyPITool()
    result = await tool.execute(action="info", package="requests")
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["name"].lower() == "requests"
    assert result["version"]
    assert result["summary"]  # summary is always present


@pytest.mark.asyncio
async def test_pypi_downloads():
    tool = PyPITool()
    result = await tool.execute(action="downloads", package="requests", period="month")
    # pypistats may rate limit; accept either success or rate-limit error
    if "error" in result and "rate limit" in result["error"].lower():
        pytest.skip("PyPI Stats rate limited")
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["downloads_last_month"] > 0
    assert result["downloads_last_day"] >= 0


@pytest.mark.asyncio
async def test_pypi_versions():
    tool = PyPITool()
    result = await tool.execute(action="versions", package="requests", limit=5)
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["total_versions"] > 0
    assert len(result["versions"]) > 0


@pytest.mark.asyncio
async def test_pypi_not_found():
    tool = PyPITool()
    result = await tool.execute(action="info", package="this-package-definitely-does-not-exist-xyz123")
    assert "error" in result


# ── yfinance ──

@pytest.mark.asyncio
async def test_yfinance_company_info():
    tool = YFinanceTool()
    result = await tool.execute(action="info", ticker="MSFT")
    if "error" in result and "rate limited" in result["error"].lower():
        pytest.skip("Yahoo Finance rate limited")
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["ticker"] == "MSFT"
    assert result["name"]
    assert result["market_cap"] > 0


@pytest.mark.asyncio
async def test_yfinance_financials():
    tool = YFinanceTool()
    result = await tool.execute(action="financials", ticker="AAPL")
    if "error" in result:
        if "rate limited" in result["error"].lower() or "no financial data" in result["error"].lower():
            pytest.skip("Yahoo Finance rate limited or no data available")
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["ticker"] == "AAPL"
    assert len(result["periods"]) > 0


@pytest.mark.asyncio
async def test_yfinance_stock_history():
    tool = YFinanceTool()
    result = await tool.execute(action="stock", ticker="GOOGL", period="3mo")
    if "error" in result:
        err = result["error"].lower()
        if "rate limited" in err or "none" in err or "no stock data" in err:
            pytest.skip("Yahoo Finance rate limited or no data")
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["ticker"] == "GOOGL"
    assert result["latest_close"] > 0
    assert result["period_high"] > 0


@pytest.mark.asyncio
async def test_yfinance_search():
    tool = YFinanceTool()
    result = await tool.execute(action="search", query="Microsoft")
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["total"] > 0
    assert any("MSFT" in r["ticker"] for r in result["results"])


@pytest.mark.asyncio
async def test_yfinance_not_found():
    tool = YFinanceTool()
    result = await tool.execute(action="info", ticker="INVALIDTICKERXYZ")
    assert "error" in result
