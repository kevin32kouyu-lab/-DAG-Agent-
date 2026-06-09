#!/usr/bin/env python
"""
预灌工具缓存脚本 — 提前用 bypass 模式跑一遍工具调用，把响应存到 SQLite 缓存。

用法:
  # 只预灌某个工具
  python scripts/warmup_cache.py --targets 飞书 钉钉 --tool serper_search

  # 按 demo 模板预灌所有工具（跑一次完整 demo 流程）
  python scripts/warmup_cache.py --targets 飞书 钉钉 --template demo

  # 查看缓存统计
  python scripts/warmup_cache.py --stats
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# 确保项目根在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 加载 .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from src.agents.tools.cache import tool_cache
from src.agents.tools.base import ToolRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("warmup_cache")


def _build_full_registry() -> ToolRegistry:
    """注册 demo 模板需要的所有工具（独立 registry）。"""
    reg = ToolRegistry()
    from src.agents.tools.serper_tool import SerperSearchTool
    from src.agents.tools.firecrawl_tool import FirecrawlTool
    from src.agents.tools.newsapi_tool import NewsAPITool
    from src.agents.tools.reddit_tool import RedditTool
    from src.agents.tools.producthunt_tool import ProductHuntTool
    from src.agents.tools.social_media_tool import SocialMediaTool
    from src.agents.tools.github_tool import GitHubTool
    from src.agents.tools.web_tools import WebScrapeTool, BatchWebScrapeTool

    reg.register(SerperSearchTool)
    reg.register(FirecrawlTool)
    reg.register(NewsAPITool)
    reg.register(RedditTool)
    reg.register(ProductHuntTool)
    reg.register(SocialMediaTool)
    reg.register(GitHubTool)
    reg.register(WebScrapeTool)
    reg.register(BatchWebScrapeTool)
    return reg


# 全局 registry（在 main 中初始化）
_REGISTRY: ToolRegistry | None = None


async def _call_tool(tool_name: str, params: dict) -> dict:
    """调用工具并把响应灌入缓存。"""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_full_registry()

    tool = _REGISTRY.get(tool_name)
    if not tool:
        logger.warning("    ⚠️  tool not registered: %s", tool_name)
        return {"error": f"Tool '{tool_name}' not registered"}

    # 直接调 execute（不走缓存）
    try:
        result = await tool.execute(**params)
    except Exception as e:
        logger.warning("    ⚠️  exception calling %s: %s", tool_name, e)
        return {"error": str(e)}

    # 手动写回缓存（即使在 bypass 模式下也要写）
    if isinstance(result, dict) and "error" not in result:
        key = tool_cache._make_key(tool_name, params)
        tool_cache._store(key, tool_name, result)
        n_results = len(result.get("results", [])) if isinstance(result.get("results"), list) else "?"
        logger.info("    ✅ cached %s (results=%s)", tool_name, n_results)
    else:
        err = result.get("error", "?") if isinstance(result, dict) else "?"
        logger.warning("    ⚠️  skipped (error): %s — %s", tool_name, err)
    return result


async def warmup_serper(targets: list[str]):
    """预灌 Serper 搜索（中英文常用查询）。"""
    queries = []
    for t in targets:
        queries.append((t, {"query": t, "gl": "cn", "hl": "zh-cn", "num": 10}))
        queries.append((t, {"query": f"{t} 定价", "gl": "cn", "hl": "zh-cn", "num": 10}))
        queries.append((t, {"query": f"{t} 功能", "gl": "cn", "hl": "zh-cn", "num": 10}))
        queries.append((t, {"query": f"{t} 用户评价 口碑", "gl": "cn", "hl": "zh-cn", "num": 10}))
        queries.append((t, {"query": f"{t} features pricing", "gl": "us", "hl": "en", "num": 10}))
    for name, params in queries:
        logger.info("🔄 Serper: %s (%s)", name, params.get("gl", "cn"))
        await _call_tool("serper_search", params)


async def warmup_newsapi(targets: list[str]):
    """预灌 NewsAPI 新闻搜索。"""
    for t in targets:
        logger.info("🔄 NewsAPI: %s", t)
        await _call_tool("newsapi", {
            "action": "everything", "query": t, "language": "zh", "limit": 10,
        })
        await _call_tool("newsapi", {
            "action": "everything", "query": t, "language": "en", "limit": 10,
        })


async def warmup_firecrawl(targets: list[str]):
    """预灌 Firecrawl 网站抓取（先用 serper 找 URL）。"""
    # 先用 serper 找到官网
    for t in targets:
        result = await _call_tool("serper_search", {"query": t, "gl": "cn", "hl": "zh-cn", "num": 5})
        urls = []
        for r in result.get("results", []):
            url = r.get("url", "")
            if url and not any(skip in url for skip in ("baidu.com", "weibo.com", "zhihu.com")):
                urls.append(url)
        # 抓前 2 个（首页 + 定价页）
        scraped_urls = set()
        for url in urls:
            if len(scraped_urls) >= 2:
                break
            if url in scraped_urls:
                continue
            logger.info("🔄 Firecrawl scrape: %s", url)
            await _call_tool("firecrawl", {"action": "scrape", "url": url})
            scraped_urls.add(url)


async def warmup_reddit(targets: list[str]):
    """预灌 Reddit 用户讨论。"""
    for t in targets:
        logger.info("🔄 Reddit: %s", t)
        await _call_tool("reddit", {"action": "search", "query": t})


async def warmup_producthunt(targets: list[str]):
    """预灌 Product Hunt 产品评分。"""
    for t in targets:
        logger.info("🔄 ProductHunt: %s", t)
        await _call_tool("producthunt", {"query": t})


async def warmup_social_media(targets: list[str]):
    """预灌社交媒体（小红书/知乎/微博）。"""
    platforms = ["xiaohongshu", "zhihu", "weibo"]
    for t in targets:
        for platform in platforms:
            logger.info("🔄 SocialMedia (%s): %s", platform, t)
            await _call_tool("social_media", {
                "action": "search", "platform": platform, "query": t, "limit": 10,
            })


async def warmup_github(targets: list[str]):
    """预灌 GitHub 搜索。"""
    for t in targets:
        logger.info("🔄 GitHub: %s", t)
        await _call_tool("github", {"action": "search", "query": t})


async def warmup_all(targets: list[str]):
    """按 demo 模板需要的工具集预灌。"""
    logger.info("=== 开始预灌缓存，targets=%s ===", targets)
    await warmup_serper(targets)
    await warmup_firecrawl(targets)
    await warmup_newsapi(targets)
    await warmup_reddit(targets)
    await warmup_producthunt(targets)
    await warmup_social_media(targets)
    await warmup_github(targets)
    stats = tool_cache.stats()
    logger.info("=== 预灌完成 ===")
    logger.info("缓存统计: %s", stats)


async def main():
    parser = argparse.ArgumentParser(description="预灌工具缓存")
    parser.add_argument("--targets", nargs="+", default=["飞书", "钉钉"],
                        help="竞品名称列表（默认：飞书 钉钉）")
    parser.add_argument("--tool", type=str, default="",
                        help="指定预灌某个工具（空=全部）")
    parser.add_argument("--template", type=str, default="",
                        help="按模板预灌：'demo' = 按 demo 模板需要的工具集")
    parser.add_argument("--stats", action="store_true",
                        help="只查看缓存统计，不执行预灌")
    parser.add_argument("--clear", type=str, nargs="?", const="all", default="",
                        help="清空缓存：--clear 或 --clear serper_search")

    args = parser.parse_args()

    if args.stats:
        stats = tool_cache.stats()
        print(f"缓存统计: mode={stats.get('mode')}")
        print(f"  总条目: {stats.get('total_entries', 0)}")
        print(f"  内存条目: {stats.get('memory_entries', 0)}")
        for tool_name, count in stats.get("by_tool", {}).items():
            print(f"  - {tool_name}: {count}")
        return

    if args.clear:
        if args.clear == "all":
            count = tool_cache.clear()
            print(f"已清空全部缓存 ({count} 条)")
        else:
            count = tool_cache.clear(args.clear)
            print(f"已清空 {args.clear} 缓存 ({count} 条)")
        return

    # 设置 bypass 模式确保结果落盘
    os.environ["TOOL_CACHE_MODE"] = "bypass"

    if args.tool:
        # 只预灌指定工具
        tool_map = {
            "serper_search": warmup_serper,
            "newsapi": warmup_newsapi,
            "firecrawl": warmup_firecrawl,
            "reddit": warmup_reddit,
            "producthunt": warmup_producthunt,
            "social_media": warmup_social_media,
            "github": warmup_github,
        }
        fn = tool_map.get(args.tool)
        if fn:
            await fn(args.targets)
        else:
            print(f"Unknown tool: {args.tool}. Available: {list(tool_map.keys())}")
            sys.exit(1)
    else:
        await warmup_all(args.targets)


if __name__ == "__main__":
    asyncio.run(main())