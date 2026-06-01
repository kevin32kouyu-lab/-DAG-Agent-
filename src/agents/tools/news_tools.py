import httpx
import xml.etree.ElementTree as ET
from typing import Any
from datetime import datetime, timezone
from src.agents.tools.base import ToolBase


class GoogleNewsTool(ToolBase):
    name = "google_news"
    description = (
        "Search Google News RSS for recent articles about a product, company, or topic. "
        "Returns headlines, source, publication date, and URLs. "
        "Free, no API key required. Best for recent (last 30 days) news coverage."
    )
    param_schema = {
        "query": {"type": "string", "description": "Search query (company/product name, topic)"},
        "limit": {"type": "integer", "description": "Max results (default 15, max 100)"},
        "when": {"type": "string", "description": "Time filter: 1d, 7d, 30d (default 7d)"},
    }

    BASE_RSS = "https://news.google.com/rss/search"

    async def execute(self, **kwargs) -> dict[str, Any]:
        query = kwargs.get("query", "")
        if not query:
            return {"error": "query is required", "results": []}

        limit = min(int(kwargs.get("limit", 15)), 100)
        when = kwargs.get("when", "7d")

        q = f"{query} when:{when}" if when else query

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self.BASE_RSS,
                    params={"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"},
                    headers={"User-Agent": "CompAgent/1.0"},
                )
                if resp.status_code != 200:
                    return {"query": query, "error": f"HTTP {resp.status_code}", "results": []}

            root = ET.fromstring(resp.text)
            results = []
            for item in root.iter("item"):
                if len(results) >= limit:
                    break

                title = ""
                link = ""
                source = ""
                pub_date = ""

                for child in item:
                    tag = child.tag.lower() if "}" not in child.tag else child.tag.split("}", 1)[1]
                    if tag == "title":
                        title = (child.text or "").strip()
                    elif tag == "link":
                        link = (child.text or "").strip()
                    elif tag == "source":
                        source = (child.text or "").strip()
                        # source may have a url attribute
                        if "url" in child.attrib:
                            source = source or child.attrib["url"]
                    elif tag == "pubdate":
                        pub_date = (child.text or "").strip()

                if title:
                    results.append({
                        "title": title,
                        "link": link,
                        "source": source,
                        "pub_date": pub_date,
                    })

            return {
                "query": query,
                "when": when,
                "total_results": len(results),
                "results": results,
            }

        except ET.ParseError as e:
            return {"query": query, "error": f"Failed to parse RSS XML: {e}", "results": []}
        except Exception as e:
            return {"query": query, "error": f"Google News query failed: {e}", "results": []}
