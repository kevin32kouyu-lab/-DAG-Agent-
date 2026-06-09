"""
Yahoo Finance 工具 — 查询公司财务数据、股票信息。

完全免费，无需 API key，通过 yfinance 库访问。
安装: pip install yfinance
"""

import logging
from typing import Any
from src.agents.tools.base import ToolBase

logger = logging.getLogger(__name__)


class YFinanceTool(ToolBase):
    name = "yfinance"
    description = (
        "Query Yahoo Finance for company financial data, stock prices, and key metrics. "
        "Use to assess public company health: revenue, margins, market cap, P/E ratio. "
        "Also useful for comparing publicly traded competitors. "
        "Completely free, no API key required (uses yfinance library)."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "info (company profile + key metrics), financials (income statement), "
                           "stock (price history), search (find ticker by name)",
        },
        "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. 'MSFT', 'AAPL')"},
        "query": {"type": "string", "description": "Company name to search (for action=search)"},
        "period": {
            "type": "string",
            "description": "Stock history period: '1mo', '3mo', '6mo', '1y', '5y' (default '1y')",
        },
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "info")

        try:
            import yfinance as yf
        except ImportError:
            return {
                "error": "yfinance not installed. Run: pip install yfinance",
                "results": [],
            }

        try:
            if action == "info":
                return await self._company_info(yf, kwargs.get("ticker", ""))
            elif action == "financials":
                return await self._financials(yf, kwargs.get("ticker", ""))
            elif action == "stock":
                return await self._stock_history(
                    yf,
                    kwargs.get("ticker", ""),
                    kwargs.get("period", "1y"),
                )
            elif action == "search":
                return await self._search(yf, kwargs.get("query", ""))
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            logger.warning("yfinance query failed: %s", e)
            return {"error": f"Yahoo Finance query failed: {e}", "results": []}

    def _run_sync(self, func, *args):
        """Run yfinance synchronous calls. yfinance is sync-only."""
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, func, *args)

    async def _company_info(self, yf, ticker: str) -> dict[str, Any]:
        if not ticker:
            return {"error": "ticker is required"}

        def _fetch():
            t = yf.Ticker(ticker)
            info = t.info
            if not info or info.get("trailingPegRatio") is None and not info.get("sector"):
                return None
            return {
                "ticker": ticker,
                "name": info.get("shortName", ""),
                "full_name": info.get("longName", ""),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "description": (info.get("longBusinessSummary") or "")[:1000],
                "website": info.get("website", ""),
                "employees": info.get("fullTimeEmployees", 0),
                "country": info.get("country", ""),
                "city": info.get("city", ""),
                "market_cap": info.get("marketCap", 0),
                "enterprise_value": info.get("enterpriseValue", 0),
                "trailing_pe": info.get("trailingPE", 0),
                "forward_pe": info.get("forwardPE", 0),
                "price_to_book": info.get("priceToBook", 0),
                "revenue": info.get("totalRevenue", 0),
                "revenue_growth": info.get("revenueGrowth", 0),
                "gross_margins": info.get("grossMargins", 0),
                "operating_margins": info.get("operatingMargins", 0),
                "profit_margins": info.get("profitMargins", 0),
                "debt_to_equity": info.get("debtToEquity", 0),
                "return_on_equity": info.get("returnOnEquity", 0),
                "current_price": info.get("currentPrice", 0),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh", 0),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow", 0),
                "dividend_yield": info.get("dividendYield", 0),
                "beta": info.get("beta", 0),
                "currency": info.get("currency", ""),
            }

        result = await self._run_sync(_fetch)
        if result is None:
            return {"error": f"Ticker '{ticker}' not found or no data available"}
        return result

    async def _financials(self, yf, ticker: str) -> dict[str, Any]:
        if not ticker:
            return {"error": "ticker is required"}

        def _fetch():
            t = yf.Ticker(ticker)
            fin = t.financials
            if fin is None or fin.empty:
                return None

            result = {"ticker": ticker, "periods": []}
            for col in fin.columns[:4]:  # Last 4 periods
                period_data = {"period": str(col.date()) if hasattr(col, "date") else str(col)}
                for idx in fin.index:
                    val = fin.loc[idx, col]
                    if val is not None and str(val) != "nan":
                        period_data[idx.lower().replace(" ", "_")] = float(val)
                result["periods"].append(period_data)
            return result

        result = await self._run_sync(_fetch)
        if result is None:
            return {"error": f"No financial data for '{ticker}'"}
        return result

    async def _stock_history(self, yf, ticker: str, period: str) -> dict[str, Any]:
        if not ticker:
            return {"error": "ticker is required"}

        valid_periods = ("1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max")
        if period not in valid_periods:
            period = "1y"

        def _fetch():
            t = yf.Ticker(ticker)
            hist = t.history(period=period)
            if hist is None or hist.empty:
                return None

            # Summary stats
            if len(hist) == 0:
                return None
            latest = hist.iloc[-1]
            earliest = hist.iloc[0]
            return {
                "ticker": ticker,
                "period": period,
                "latest_close": round(float(latest["Close"]), 2),
                "latest_date": str(hist.index[-1].date()),
                "period_start": str(hist.index[0].date()),
                "period_start_close": round(float(earliest["Close"]), 2),
                "period_change_pct": round(
                    (float(latest["Close"]) - float(earliest["Close"])) / float(earliest["Close"]) * 100, 2
                ),
                "period_high": round(float(hist["High"].max()), 2),
                "period_low": round(float(hist["Low"].min()), 2),
                "avg_volume": int(hist["Volume"].mean()),
                "data_points": len(hist),
            }

        result = await self._run_sync(_fetch)
        if result is None:
            return {"error": f"No stock data for '{ticker}'"}
        return result

    async def _search(self, yf, query: str) -> dict[str, Any]:
        if not query:
            return {"error": "query is required"}

        def _fetch():
            # yfinance doesn't have a search API; use the Lookup endpoint
            try:
                import httpx
                resp = httpx.get(
                    "https://query2.finance.yahoo.com/v1/finance/search",
                    params={"q": query, "quotesCount": 10, "newsCount": 0},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for quote in data.get("quotes", []):
                        results.append({
                            "ticker": quote.get("symbol", ""),
                            "name": quote.get("shortname", ""),
                            "exchange": quote.get("exchange", ""),
                            "type": quote.get("quoteType", ""),
                            "sector": quote.get("sector", ""),
                            "industry": quote.get("industry", ""),
                        })
                    return results
            except Exception:
                pass

            # Fallback: try the query as a ticker directly
            try:
                t = yf.Ticker(query)
                info = t.info
                if info and info.get("shortName"):
                    return [{
                        "ticker": query.upper(),
                        "name": info.get("shortName", ""),
                        "exchange": info.get("exchange", ""),
                        "type": info.get("quoteType", ""),
                        "sector": info.get("sector", ""),
                        "industry": info.get("industry", ""),
                    }]
            except Exception:
                pass
            return []

        results = await self._run_sync(_fetch)
        return {"query": query, "total": len(results), "results": results}
