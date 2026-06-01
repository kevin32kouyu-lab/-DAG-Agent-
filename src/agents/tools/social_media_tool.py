"""
社交媒体舆情采集工具 — 基于 Playwright 浏览器自动化。

参考 MediaCrawler 架构:
  - Playwright 启动真实浏览器, 模拟登录态和 JS 执行
  - 异步并发, 避免逆向工程平台的签名算法
  - 每个平台独立处理, 统一返回结构化数据

支持平台 (仅公开数据, 无需登录):
  - 小红书 (xiaohongshu): 搜索笔记、热门话题讨论度
  - 知乎 (zhihu): 品牌讨论、问答热度
  - 微博 (weibo): 实时舆情热度

采集的竞品数据:
  - 社交媒体讨论量 (品牌声量)
  - 用户情感倾向 (正面/负面关键词)
  - 讨论话题分布
  - 竞品对比热度

注意:
  - 仅爬取公开可见内容, 不登录、不抓私密数据
  - 反爬策略: 随机延迟、浏览器指纹伪装
  - 每次调用限制搜索 1-2 轮, 避免触发风控
"""

import asyncio
import random
from typing import Any
from src.agents.tools.base import ToolBase


class SocialMediaTool(ToolBase):
    name = "social_media"
    description = (
        "Search social media platforms (Xiaohongshu, Zhihu, Weibo) for brand mentions, "
        "user discussions, and competitive sentiment. "
        "Uses browser automation (Playwright) to access public content — no login required. "
        "Returns discussion volume, popular topics, and sentiment hints. "
        "Best for: measuring brand awareness and user sentiment on Chinese social platforms."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "search (search brand/product mentions), trending (popular topics on platform)",
        },
        "platform": {
            "type": "string",
            "description": "Target platform: 'xiaohongshu' (小红书), 'zhihu' (知乎), 'weibo' (微博)",
        },
        "query": {
            "type": "string",
            "description": "Search query — brand name, product name, or keyword",
        },
        "limit": {"type": "integer", "description": "Max results (default 10, max 20)"},
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "search")
        platform = kwargs.get("platform", "xiaohongshu")
        query = kwargs.get("query", "")
        limit = min(int(kwargs.get("limit", 10)), 20)

        if action == "search" and not query:
            return {"error": "query is required for search action", "results": []}

        try:
            if platform == "xiaohongshu":
                return await self._search_xiaohongshu(query, limit)
            elif platform == "zhihu":
                return await self._search_zhihu(query, limit)
            elif platform == "weibo":
                return await self._search_weibo(query, limit)
            else:
                return {"error": f"Unknown platform: {platform}. Supported: xiaohongshu, zhihu, weibo"}
        except Exception as e:
            return {
                "platform": platform,
                "query": query,
                "error": f"Social media crawl failed: {e}",
                "results": [],
            }

    async def _launch_browser(self):
        """Launch a Playwright browser with anti-detection measures."""
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        browser = await self._pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        # Hide automation signals
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)
        return browser, context

    async def _search_xiaohongshu(self, query: str, limit: int) -> dict:
        """Search 小红书 for brand mentions."""
        browser, context = await self._launch_browser()
        page = await context.new_page()

        try:
            # Navigate to Xiaohongshu search
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={query}&type=51"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)

            # Wait for content to load (anti-bot detection may block)
            await asyncio.sleep(random.uniform(2, 4))

            # Try to extract post data from the page
            results = await page.evaluate("""
                () => {
                    const items = [];
                    // Try multiple selectors for Xiaohongshu note cards
                    const cards = document.querySelectorAll(
                        '[class*="note-item"], [class*="feeds-page"] a[href*="/explore/"], section.note-item'
                    );
                    cards.forEach(card => {
                        const title = card.querySelector('[class*="title"], .title')?.innerText || '';
                        const link = card.href || card.querySelector('a')?.href || '';
                        const likes = card.querySelector('[class*="like"] span, .like-count')?.innerText || '0';
                        items.push({ title, url: link, engagement: likes });
                    });
                    return items;
                }
            """)

            # If no structured results found, try text extraction
            if not results:
                body_text = await page.evaluate("() => document.body.innerText")
                # Parse any visible note titles from the text
                lines = [l.strip() for l in body_text.split("\n") if len(l.strip()) > 10]
                results = [{"title": l, "url": search_url} for l in lines[:limit]]

            return {
                "platform": "xiaohongshu",
                "query": query,
                "total_results": len(results),
                "results": results[:limit],
                "sentiment_note": "Extract topics/keywords from titles to infer sentiment",
            }
        except Exception as e:
            return {"platform": "xiaohongshu", "query": query, "error": str(e), "results": []}
        finally:
            await browser.close()
            await self._pw.stop()

    async def _search_zhihu(self, query: str, limit: int) -> dict:
        """Search 知乎 for brand discussions."""
        browser, context = await self._launch_browser()
        page = await context.new_page()

        try:
            search_url = f"https://www.zhihu.com/search?type=content&q={query}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)

            await asyncio.sleep(random.uniform(2, 4))

            results = await page.evaluate("""
                () => {
                    const items = [];
                    const cards = document.querySelectorAll(
                        '[class*="List-item"], .SearchResult-Card, [class*="SearchResult"]'
                    );
                    cards.forEach(card => {
                        const title = card.querySelector('h2, [class*="title"], .Highlight')?.innerText || '';
                        const link = card.querySelector('a[href*="/question/"], a[href*="/answer/"]')?.href || '';
                        const votes = card.querySelector('[class*="Vote"], [class*="voteCount"]')?.innerText || '0';
                        const comments = card.querySelector('[class*="comments"]')?.innerText || '0';
                        items.push({
                            title: title.trim(),
                            url: link,
                            upvotes: votes,
                            comments: comments,
                        });
                    });
                    return items;
                }
            """)

            if not results:
                body_text = await page.evaluate("() => document.body.innerText")
                lines = [l.strip() for l in body_text.split("\n") if len(l.strip()) > 15]
                results = [{"title": l, "url": search_url, "upvotes": "0"} for l in lines[:limit]]

            return {
                "platform": "zhihu",
                "query": query,
                "total_results": len(results),
                "results": results[:limit],
            }
        except Exception as e:
            return {"platform": "zhihu", "query": query, "error": str(e), "results": []}
        finally:
            await browser.close()
            await self._pw.stop()

    async def _search_weibo(self, query: str, limit: int) -> dict:
        """Search 微博 for real-time brand mentions."""
        browser, context = await self._launch_browser()
        page = await context.new_page()

        try:
            search_url = f"https://s.weibo.com/weibo?q={query}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)

            await asyncio.sleep(random.uniform(2, 4))

            results = await page.evaluate("""
                () => {
                    const items = [];
                    const cards = document.querySelectorAll('[class*="card-wrap"], .card, [action-type="feed_list_item"]');
                    cards.forEach(card => {
                        const text = card.querySelector('[class*="txt"], .text, p')?.innerText || '';
                        const author = card.querySelector('[class*="name"], .nick-name')?.innerText || '';
                        const link = card.querySelector('a[href*="/status/"]')?.href || '';
                        const reposts = card.querySelector('[class*="repost"], .forward')?.innerText || '';
                        items.push({
                            content: text.trim().substring(0, 200),
                            author: author.trim(),
                            url: link,
                            engagement: reposts.trim(),
                        });
                    });
                    return items;
                }
            """)

            if not results:
                body_text = await page.evaluate("() => document.body.innerText")
                lines = [l.strip() for l in body_text.split("\n") if len(l.strip()) > 10]
                results = [{"content": l, "author": "", "url": search_url} for l in lines[:limit]]

            return {
                "platform": "weibo",
                "query": query,
                "total_results": len(results),
                "results": results[:limit],
                "note": "Real-time data — upvote counts reflect current engagement",
            }
        except Exception as e:
            return {"platform": "weibo", "query": query, "error": str(e), "results": []}
        finally:
            await browser.close()
            await self._pw.stop()
