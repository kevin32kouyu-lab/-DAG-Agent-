#!/usr/bin/env python
"""
Demo 数据预灌脚本 — 用免费/已有爬虫工具爬取竞品数据，灌入缓存 + 知识图谱。

分阶段执行：
  python scripts/enrich_demo_data.py --topic collab --phase search   # 多引擎搜索 URL
  python scripts/enrich_demo_data.py --topic collab --phase scrape   # 批量抓取网页
  python scripts/enrich_demo_data.py --topic collab --phase pipeline # 预跑 DAG 生成图谱
  python scripts/enrich_demo_data.py --topic collab --phase all      # 一键全跑

Topic 列表:
  collab  — 协同办公: 飞书 vs 钉钉 vs 企业微信
  ai-chat — AI 大模型: 豆包 vs Kimi vs 通义千问
  short-video — 短视频: 抖音 vs 快手 vs 视频号
  ai-ide  — AI 编程: Trae vs Cursor vs Copilot
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import httpx
from bs4 import BeautifulSoup

from src.agents.tools.cache import tool_cache
from src.agents.tools.serper_tool import SerperSearchTool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("enrich_demo")

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════

TOPICS = {
    "collab": {
        "id": "collab",
        "name": "协同办公",
        "products": ["飞书", "钉钉", "企业微信"],
        "scenario": "saas",
        "collection_depth": "demo",
    },
    "ai-chat": {
        "id": "ai-chat",
        "name": "AI 大模型助手",
        "products": ["豆包", "Kimi", "通义千问"],
        "scenario": "app",
        "collection_depth": "demo",
    },
    "short-video": {
        "id": "short-video",
        "name": "短视频平台",
        "products": ["抖音", "快手", "视频号"],
        "scenario": "app",
        "collection_depth": "demo",
    },
    "ai-ide": {
        "id": "ai-ide",
        "name": "AI 编程工具",
        "products": ["Trae", "Cursor", "GitHub Copilot"],
        "scenario": "saas",
        "collection_depth": "demo",
    },
}

# 每个产品搜中文 + 英文各 8 个 query
SEARCH_QUERIES_CN = [
    "{product}",
    "{product} 官网",
    "{product} 定价 套餐 价格",
    "{product} 功能 特点 介绍",
    "{product} 评测 测评 2025",
    "{product} 对比 竞品 vs",
    "{product} 用户评价 口碑 反馈",
    "{product} 新闻 动态 更新 2025",
]

SEARCH_QUERIES_EN = [
    "{product} official website",
    "{product} pricing plans features",
    "{product} review comparison 2025",
    "{product} vs competitor alternative",
    "{product} user reviews reddit",
    "{product} news update 2025",
    "{product} features capabilities",
    "{product} market positioning analysis",
]

# 需要特殊处理的非英文产品名
PRODUCT_NAMES_EN = {
    "飞书": "feishu lark",
    "钉钉": "dingtalk",
    "企业微信": "wecom wechat work",
    "豆包": "doubao bytedance AI",
    "Kimi": "kimi moonshot AI",
    "通义千问": "tongyi qwen alibaba AI",
    "抖音": "tiktok douyin",
    "快手": "kuaishou",
    "视频号": "wechat channels",
    "Trae": "trae bytedance IDE",
    "Cursor": "cursor AI IDE",
    "GitHub Copilot": "github copilot",
}

UA_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

UA_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
    "Mobile/15E148 Safari/604.1"
)

# ═══════════════════════════════════════════════════════════════
# Phase 1: 多引擎搜索
# ═══════════════════════════════════════════════════════════════


async def search_serper(query: str, gl: str = "cn") -> list[dict]:
    """Serper Google Search（有 API key）。"""
    tool = SerperSearchTool()
    result = await tool.execute(query=query, gl=gl, hl="zh-cn" if gl == "cn" else "en", num=10)
    if "error" in result:
        logger.warning("  Serper(%s) error: %s", gl, result.get("error", ""))
        return []
    results = result.get("results", [])
    # 写缓存
    key = tool_cache._make_key("serper_search", {"query": query, "gl": gl})
    tool_cache._store(key, "serper_search", result)
    return results


async def search_ddgs(query: str) -> list[dict]:
    """DuckDuckGo 搜索（免费无限）。"""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        loop = asyncio.get_event_loop()

        def _do():
            results = []
            for r in DDGS().text(query, max_results=10):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                    "source": "ddgs",
                })
            return results

        results = await loop.run_in_executor(None, _do)
        # 写缓存
        key = tool_cache._make_key("ddgs_search", {"query": query})
        tool_cache._store(key, "ddgs_search", {"query": query, "results": results})
        return results
    except ImportError:
        logger.debug("  DDGS: library not installed, skipping")
        return []
    except Exception as e:
        logger.debug("  DDGS error: %s", e)
        return []


async def search_sogou(query: str) -> list[dict]:
    """搜狗搜索 HTML 抓取（免费无限）。"""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                "https://www.sogou.com/web",
                params={"query": query},
                headers={"User-Agent": UA_CHROME},
            )
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for item in soup.select(".vrwrap, .rb"):
            link = item.select_one("h3 a")
            if not link:
                continue
            snippet_el = item.select_one(".str_info, .str-text-info, p, .space-txt")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            results.append({
                "title": link.get_text(strip=True),
                "url": link.get("href", ""),
                "snippet": snippet[:300],
                "source": "sogou",
            })
        return results[:10]
    except Exception as e:
        logger.debug("  Sogou error: %s", e)
        return []


async def search_baidu(query: str) -> list[dict]:
    """百度移动搜索 HTML 抓取（免费无限）。"""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                "https://m.baidu.com/s",
                params={"wd": query},
                headers={
                    "User-Agent": UA_IPHONE,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            )
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for container in soup.select(".c-result, .result"):
            title = ""
            url = ""
            for a_tag in container.select("a"):
                text = a_tag.get_text(strip=True)
                if len(text) > 4 and text not in ("大家还在搜",):
                    title = text[:100]
                    url = a_tag.get("href", "")
                    break
            if not title:
                continue

            snippet = ""
            for sel in [".summary-text_560AW", ".cu-line-clamp-3", ".c-color",
                        "span[class*='summary']", "div[class*='summary']"]:
                el = container.select_one(sel)
                if el and len(el.get_text(strip=True)) > 10:
                    snippet = el.get_text(strip=True)[:300]
                    break

            results.append({"title": title, "url": url, "snippet": snippet, "source": "baidu"})
        return results[:10]
    except Exception as e:
        logger.debug("  Baidu error: %s", e)
        return []


def _estimate_credibility(url: str, tool_name: str) -> float:
    """根据来源引擎和域名评估可信度分数。"""
    import re
    domain = url.split("/")[2] if "//" in url else ""
    # Serper (Google) 基础分更高
    base = 0.7 if tool_name == "serper_search" else 0.5
    # 权威域名加分
    high_trust = [r'wikipedia\.org', r'github\.com', r'\.gov', r'\.edu',
                  r'crunchbase\.com', r'producthunt\.com', r'reddit\.com']
    medium_trust = [r'zhihu\.com', r'jianshu\.com', r'csdn\.net', r'sspai\.com',
                    r'36kr\.com', r'infoq\.com']
    low_trust = [r'xiaohongshu\.com', r'weibo\.com', r'tieba\.baidu\.com']
    for pat in high_trust:
        if re.search(pat, domain):
            return min(base + 0.2, 1.0)
    for pat in medium_trust:
        if re.search(pat, domain):
            return min(base + 0.1, 1.0)
    for pat in low_trust:
        if re.search(pat, domain):
            return max(base - 0.1, 0.3)
    return base


def _get_english_name(product: str) -> str:
    return PRODUCT_NAMES_EN.get(product, product.lower())


# ═══════════════════════════════════════════════════════════════
# Phase 3 辅助: 专业 API 数据采集（Reddit / GitHub / ProductHunt）
# ═══════════════════════════════════════════════════════════════

async def _fetch_professional_api_context(topic_id: str, topic: dict) -> str:
    """为 Demo 数据生成采集专业 API 的结构化数据，供 LLM 上下文使用。

    对每个产品调用 Reddit / GitHub / ProductHunt API，返回格式化的 markdown 文本。
    所有 API 调用优雅降级——单个失败不影响其它数据源。
    """
    import json as json_mod

    products = topic["products"]
    parts: list[str] = []
    parts.append("\n\n=== PROFESSIONAL API DATA (enriched context) ===\n")

    # ── Reddit ──
    parts.append("## Reddit Developer Discussions\n")
    try:
        from src.agents.tools.reddit_tool import RedditTool
        reddit = RedditTool()
        for product in products:
            en_name = _get_english_name(product)
            for subreddit in ["all"]:  # r/all search is broadest coverage
                try:
                    result = await reddit.execute(
                        action="search", query=en_name, subreddit=subreddit,
                        sort="relevance", limit=10, time_range="year",
                    )
                    if result.get("total_results", 0) > 0:
                        parts.append(f"\n### Reddit results for {product} (query: {en_name})")
                        for r in result.get("results", [])[:8]:
                            parts.append(
                                f"- [{r.get('subreddit', '')}] {r.get('title', '')} "
                                f"(↑{r.get('score', 0)} · {r.get('num_comments', 0)} comments)\n"
                                f"  {r.get('selftext', '')[:300]}"
                            )
                except Exception:
                    pass
                # 只搜 all 就够了，不重复搜多个 subreddit
                break
        parts.append(f"\n_(Reddit data collected at runtime)_")
    except ImportError as e:
        parts.append(f"_(Reddit tool unavailable: {e})_")
    except Exception as e:
        logger.warning("Reddit API data collection failed: %s", e)
        parts.append(f"_(Reddit unavailable: {e})_")

    # ── GitHub ──
    parts.append("\n## GitHub Repository Data\n")
    try:
        from src.agents.tools.github_tool import GitHubTool
        github = GitHubTool()
        for product in products:
            en_name = _get_english_name(product)
            # 搜产品名找官方/主要仓库
            try:
                search_result = await github.execute(action="search", query=en_name, limit=5)
                if search_result.get("total_count", 0) > 0:
                    parts.append(f"\n### GitHub repos for {product} (query: {en_name})")
                    for repo in search_result.get("results", [])[:5]:
                        parts.append(
                            f"- **{repo.get('full_name', '')}** "
                            f"⭐{repo.get('stars', 0)} · {repo.get('language', 'N/A')} · "
                            f"topics: {', '.join(repo.get('topics', []))}\n"
                            f"  {repo.get('description', '')[:200]}"
                        )
                # 对找到的第一个仓库抓详细信息
                if search_result.get("results"):
                    first = search_result["results"][0]
                    full_name = first.get("full_name", "")
                    if "/" in full_name:
                        owner, repo_name = full_name.split("/", 1)
                        try:
                            stats = await github.execute(action="repo", owner=owner, repo=repo_name)
                            if "error" not in stats:
                                parts.append(
                                    f"  _Stats_: {stats.get('stars', 0)} stars, "
                                    f"{stats.get('forks', 0)} forks, "
                                    f"{stats.get('open_issues', 0)} open issues, "
                                    f"license: {stats.get('license', 'N/A')}"
                                )
                        except Exception:
                            pass
            except Exception:
                pass
        parts.append(f"\n_(GitHub data collected at runtime)_")
    except ImportError as e:
        parts.append(f"_(GitHub tool unavailable: {e})_")
    except Exception as e:
        logger.warning("GitHub API data collection failed: %s", e)
        parts.append(f"_(GitHub unavailable: {e})_")

    # ── ProductHunt ──
    parts.append("\n## ProductHunt Community Data\n")
    try:
        from src.agents.tools.producthunt_tool import ProductHuntTool
        ph = ProductHuntTool()
        for product in products:
            en_name = _get_english_name(product)
            try:
                result = await ph.execute(action="search", query=en_name, limit=5)
                if result.get("total_results", 0) > 0:
                    parts.append(f"\n### ProductHunt results for {product}")
                    for r in result.get("results", [])[:5]:
                        parts.append(
                            f"- **{r.get('name', '')}**: {r.get('tagline', '')}\n"
                            f"  👍{r.get('votes', 0)} · 💬{r.get('comments', 0)} · "
                            f"⭐{r.get('rating', 0)} · topics: {', '.join(r.get('topics', []))}\n"
                            f"  {r.get('description', '')[:300]}"
                        )
            except Exception:
                pass
        parts.append(f"\n_(ProductHunt data collected at runtime)_")
    except ImportError as e:
        parts.append(f"_(ProductHunt tool unavailable: {e})_")
    except Exception as e:
        logger.warning("ProductHunt API data collection failed: %s", e)
        parts.append(f"_(ProductHunt unavailable: {e})_")

    parts.append("\n=== END PROFESSIONAL API DATA ===\n")
    enriched = "\n".join(parts)
    logger.info("Professional API context: %d chars", len(enriched))
    return enriched


async def search_product(product: str) -> dict[str, list[dict]]:
    """对单个产品做全引擎搜索，返回去重 URL 列表。"""
    all_urls: dict[str, dict] = {}  # url -> {title, snippet, sources[]}

    def _add(results: list[dict]):
        for r in results:
            url = r.get("url", "")
            if not url:
                continue
            if url in all_urls:
                all_urls[url]["sources"].append(r.get("source", "?"))
            else:
                all_urls[url] = {
                    "title": r.get("title", ""),
                    "url": url,
                    "snippet": r.get("snippet", ""),
                    "sources": [r.get("source", "?")],
                }

    # 中文 query × 多引擎
    for q_template in SEARCH_QUERIES_CN:
        q = q_template.format(product=product)
        logger.info("  🔍 中文: %s", q)
        _add(await search_serper(q, gl="cn"))
        _add(await search_sogou(q))
        _add(await search_baidu(q))

    # 英文 query × Serper + DDGS
    en_name = _get_english_name(product)
    for q_template in SEARCH_QUERIES_EN:
        q = q_template.format(product=en_name)
        logger.info("  🔍 英文: %s", q)
        _add(await search_serper(q, gl="us"))
        _add(await search_ddgs(q))

    return {
        "product": product,
        "total_urls": len(all_urls),
        "urls": sorted(all_urls.values(), key=lambda u: len(u["sources"]), reverse=True),
    }


async def phase_search(topic_id: str):
    """Phase 1: 多引擎搜索，发现所有 URL。"""
    topic = TOPICS[topic_id]
    logger.info("=" * 60)
    logger.info("Phase 1: URL 发现 — %s", topic["name"])
    logger.info("  产品: %s", ", ".join(topic["products"]))
    logger.info("=" * 60)

    all_results = {}
    for product in topic["products"]:
        logger.info("搜索: %s", product)
        result = await search_product(product)
        all_results[product] = result
        logger.info("  → 去重后 %d 个 URL", result["total_urls"])

    # 保存 URL 清单
    output_path = f"data/enrich_{topic_id}_urls.json"
    os.makedirs("data", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    total = sum(r["total_urls"] for r in all_results.values())
    logger.info("Phase 1 完成: %d 个去重 URL → %s", total, output_path)

    stats = tool_cache.stats()
    logger.info("工具缓存: %d 条", stats.get("total_entries", 0))
    return all_results


# ═══════════════════════════════════════════════════════════════
# Phase 2: 批量网页抓取
# ═══════════════════════════════════════════════════════════════


async def scrape_single(url: str, sem: asyncio.Semaphore) -> dict:
    """抓取单个网页（带并发控制）。"""
    async with sem:
        from src.agents.tools.web_tools import WebScrapeTool

        tool = WebScrapeTool()
        result = await tool.execute(url=url)

        # 写缓存
        if "error" not in result:
            key = tool_cache._make_key("web_scrape", {"url": url})
            tool_cache._store(key, "web_scrape", result)
            text_len = len(result.get("text", ""))
            logger.info("  ✅ %s [%d chars] %s", url[:80], text_len, result.get("source", ""))
        else:
            logger.warning("  ❌ %s — %s", url[:80], result.get("error", "")[:60])
        return result


async def phase_scrape(topic_id: str):
    """Phase 2: 批量抓取 Phase 1 发现的 URL。"""
    topic = TOPICS[topic_id]
    url_file = f"data/enrich_{topic_id}_urls.json"

    if not os.path.exists(url_file):
        logger.error("URL 清单不存在: %s — 请先运行 phase search", url_file)
        return

    with open(url_file, "r", encoding="utf-8") as f:
        all_results = json.load(f)

    # 收集所有 URL，去重
    seen = set()
    all_urls = []
    for product, data in all_results.items():
        for u in data["urls"]:
            url = u["url"]
            if url not in seen and not any(
                skip in url
                for skip in ("baidu.com/link", "sogou.com", "weibo.com", "douyin.com/video")
            ):
                seen.add(url)
                all_urls.append(u)

    logger.info("=" * 60)
    logger.info("Phase 2: 批量网页抓取 — %s", topic["name"])
    logger.info("  待抓取: %d 个 URL", len(all_urls))
    logger.info("=" * 60)

    # 并发控制：同时最多 5 个
    sem = asyncio.Semaphore(5)
    tasks = []
    for i, u in enumerate(all_urls):
        tasks.append(scrape_single(u["url"], sem))
        if i >= 150:  # 每个 topic 最多抓 150 个 URL
            break

    results = await asyncio.gather(*tasks, return_exceptions=True)
    success = sum(1 for r in results if isinstance(r, dict) and "error" not in r)
    failed = sum(1 for r in results if isinstance(r, dict) and "error" in r)

    logger.info("Phase 2 完成: %d 成功, %d 失败", success, failed)
    stats = tool_cache.stats()
    logger.info("工具缓存: %d 条", stats.get("total_entries", 0))


# ═══════════════════════════════════════════════════════════════
# Phase 3: 预跑 Pipeline 生成知识图谱
# ═══════════════════════════════════════════════════════════════


async def phase_pipeline(topic_id: str):
    """Phase 3: 从缓存直接灌入知识图谱 + LLM 批量分析。绕过 Agent max_steps 限制。"""
    topic = TOPICS[topic_id]
    logger.info("=" * 60)
    logger.info("Phase 3: KG 直接灌入 — %s", topic["name"])
    logger.info("=" * 60)

    from openai import AsyncOpenAI
    from src.knowledge_graph.store import GraphStore
    from src.knowledge_graph.models import (
        SourceInfoNode, WebPageNode, FeatureNode, SentimentNode,
        PricingModelNode, PricingDataNode, MarketPositionNode,
        SWOTNode, ScoringNode, ReportSectionNode, ProductNode,
        GraphEdge, EdgeType,
    )

    db_path = f"data/demo_{topic_id}.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    store = GraphStore(db_path)
    task_id = f"demo_{topic_id}"
    products = topic["products"]

    llm = AsyncOpenAI(
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
        api_key=os.environ.get("OPENAI_API_KEY", ""),
    )
    llm_model = os.environ.get("LLM_DEFAULT_MODEL", "deepseek-chat")

    # ── 3a: SourceInfo + WebPage 从缓存 ──
    logger.info("3a: Layer 1 数据节点...")
    import sqlite3
    cache_db = tool_cache._db_path
    seen_urls = set()
    source_nodes, page_nodes = [], []

    if os.path.exists(cache_db):
        conn = sqlite3.connect(cache_db)
        rows = conn.execute(
            "SELECT tool_name, value FROM cache WHERE tool_name IN ('serper_search','ddgs_search')"
        ).fetchall()
        conn.close()
        for tool_name, value_raw in rows:
            try:
                for r in json.loads(value_raw).get("results", []):
                    url = r.get("url", "").strip()
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    n = SourceInfoNode(
                        url=url, domain=url.split("/")[2] if "//" in url else "",
                        label=r.get("title", "")[:200] or url,
                        credibility_score=_estimate_credibility(url, tool_name),
                        metadata={"task_id": task_id, "snippet": r.get("snippet", "")},
                    )
                    store.create_node(n)
                    source_nodes.append(n)
            except Exception:
                continue

    if os.path.exists(cache_db):
        conn = sqlite3.connect(cache_db)
        rows = conn.execute("SELECT value FROM cache WHERE tool_name='web_scrape'").fetchall()
        conn.close()
        for (value_raw,) in rows:
            try:
                d = json.loads(value_raw)
                if "error" in d or not d.get("url"):
                    continue
                n = WebPageNode(
                    url=d["url"], title=d.get("title", "")[:200],
                    text=d.get("text", "")[:5000],
                    key_paragraphs=d.get("key_paragraphs", [])[:15],
                    label=d.get("title", "")[:200] or d["url"],
                    metadata={"task_id": task_id},
                )
                store.create_node(n)
                page_nodes.append(n)
            except Exception:
                continue
    logger.info("  SourceInfo: %d  WebPage: %d", len(source_nodes), len(page_nodes))

    # ── 3b: Product 节点 ──
    logger.info("3b: Product 节点...")
    for p in products:
        store.create_node(ProductNode(name=p, category=topic["scenario"], label=p, metadata={"task_id": task_id}))

    # ── 3c: 构建上下文 ──
    ctx_parts = []
    for p in products:
        ctx_parts.append(f"\n=== PRODUCT: {p} ===")
        for n in source_nodes:
            snip = n.metadata.get("snippet", "")
            if p.lower() in n.label.lower() or p.lower() in snip.lower():
                ctx_parts.append(f"URL [{n.domain}]: {n.label} | {snip[:200]}")
                if len(ctx_parts) > 400:
                    break
        for n in page_nodes:
            if p.lower() in n.title.lower() or p.lower() in n.text[:300].lower():
                ctx_parts.append(f"PAGE: {n.title}\n{n.text[:800]}")
                if len(ctx_parts) > 500:
                    break
    context = "\n".join(ctx_parts)[:22000]

    # ── 3c-0: 调用专业 API 丰富上下文（Reddit + GitHub + ProductHunt）──
    logger.info("3c-0: 调用专业 API 采集社区/仓库/产品数据...")
    try:
        api_context = await _fetch_professional_api_context(topic_id, topic)
        # 追加到 context，总长度控制在 35K 以内
        context = (context + api_context)[:35000]
        logger.info("  合并后 context: %d chars", len(context))
    except Exception as e:
        logger.warning("  专业 API 采集失败（不影响主流程）: %s", e)

    async def _llm_json(prompt: str, max_tokens=4096) -> dict:
        resp = await llm.chat.completions.create(
            model=llm_model, temperature=0.3, max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0] if "```" in text[3:] else text
        return json.loads(text)

    # ── 3c-1: Feature ──
    logger.info("3c-1: Feature 分析...")
    try:
        # 归一化 prompt：用通用能力名而非产品独有功能名，避免矩阵全是 unknown
        feature_prompt = (
            f"Products: {', '.join(products)}\n\n{context}\n\n"
            "For ALL products together, identify 8-12 COMMON CAPABILITY DIMENSIONS "
            "(NOT product-specific feature names). "
            "Use GENERIC capability names IN CHINESE: '在线表格/多维表格' NOT '飞书多维表格', "
            "'强提醒消息' NOT 'DING消息强提醒', "
            "'在线文档协作' NOT '企微文档协作', "
            "'AI 代码补全' NOT 'Trae AI补全', "
            "'多文件编辑' NOT 'Composer多文件编辑'.\n\n"
            "For each product×capability, set maturity (ga/beta/experimental/unknown) based on evidence. "
            "If a product clearly has this capability (industry standard) but no explicit evidence, default to 'ga', NOT 'unknown'. "
            "Only use 'unknown' for capabilities truly unclear for that product.\n\n"
            "Return ONLY JSON: "
            '{"features":[{"product":"X","name":"Generic Capability Name","category":"UI|AI|Collaboration|API|Security|Analytics|Mobile|Integration","description":"1 sentence","maturity":"ga|beta|experimental|unknown","differentiation":"unique|advantage|parity|disadvantage"},...]}'
        )
        data = await _llm_json(feature_prompt, max_tokens=8192)

        cnt = 0
        for f in data.get("features", []):
            store.create_node(FeatureNode(
                product=f["product"], name=f["name"], category=f.get("category", "General"),
                description=f.get("description", ""), maturity=f.get("maturity", "unknown"),
                differentiation=f.get("differentiation", "parity"),
                label=f["name"], metadata={"task_id": task_id},
            ))
            cnt += 1
        logger.info("  FeatureNode: %d", cnt)
    except Exception as e:
        logger.warning("  Feature failed: %s", e)

    # ── 3c-2: Sentiment ──
    logger.info("3c-2: Sentiment 分析...")
    try:
        # 场景适配：AI 编程工具需要从训练知识补充开发者社区反馈
        is_dev_tool = any(p in products for p in ["Trae", "Cursor", "GitHub Copilot", "Copilot"])
        supplement_hint = ""
        if is_dev_tool:
            supplement_hint = (
                "If web context lacks developer feedback, supplement with your training knowledge "
                "about Reddit r/cursor, r/githubcopilot, Hacker News discussions, and developer forums. "
                "Mark supplemented items with topic suffix '(estimated)' to distinguish from crawled data. "
            )
        sentiment_prompt = (
            f"Products: {', '.join(products)}\n\n{context[:15000]}\n\n"
            f"{supplement_hint}"
            "For EACH product, analyze 3-6 sentiment topics. "
            "Cover the SAME topics for ALL products to enable comparison. "
            "Required topics: pricing, usability, performance, features. "
            "Return ONLY JSON: "
            '{"sentiments":[{"product":"X","topic":"pricing|usability|performance|support|features|onboarding",'
            '"sentiment_score":0.8,"trend":"improving|stable|declining","key_quotes":["..."]},...]}'
        )
        data = await _llm_json(sentiment_prompt, max_tokens=8192)

        cnt = 0
        for s in data.get("sentiments", []):
            store.create_node(SentimentNode(
                product=s["product"], topic=s["topic"],
                sentiment_score=s.get("sentiment_score", 0),
                trend=s.get("trend", "stable"), key_quotes=s.get("key_quotes", []),
                label=f"{s['product']} - {s['topic']}", metadata={"task_id": task_id},
            ))
            cnt += 1
        logger.info("  SentimentNode: %d", cnt)
    except Exception as e:
        logger.warning("  Sentiment failed: %s", e)

    # ── 3c-3: Pricing ──
    logger.info("3c-3: Pricing 分析...")
    try:
        pricing_prompt = (
            f"Products: {', '.join(products)}\n\n{context[:15000]}\n\n"
            "For EACH of the {len(products)} products listed above, analyze pricing. "
            "You MUST return pricing data for ALL {len(products)} products — the array must have {len(products)} entries. "
            "Normalize plans into standard tiers: Free / Starter / Pro / Business / Enterprise. "
            "If exact price unknown, estimate from context and set value_score to 0.3. "
            "value_score MUST be a number between 0.0 and 1.0 — NEVER null. "
            "Prices should be in the product's native currency; add currency field. "
            "Return ONLY JSON: "
            '{"pricing":[{"product":"X","strategy":"freemium|usage-based|per-seat|flat-rate|hybrid",'
            '"target_segment":"individual|SMB|mid-market|enterprise","value_score":0.5,'
            '"plans":[{"plan_name":"Free","price":0,"currency":"CNY","billing_cycle":"monthly","features":["..."]}]},...]}'
        )
        data = await _llm_json(pricing_prompt, max_tokens=8192)

        for p_item in data.get("pricing", []):
            product_name = p_item.get("product", "Unknown")
            vs = p_item.get("value_score")
            if vs is None or not isinstance(vs, (int, float)):
                vs = 0.5
            vs = float(vs)
            strategy = p_item.get("strategy", "") or "freemium"
            segment = p_item.get("target_segment", "") or "SMB"
            pm = PricingModelNode(
                product=product_name, strategy=strategy,
                target_segment=segment,
                value_score=vs,
                label=f"{product_name} 定价模型", metadata={"task_id": task_id},
            )
            store.create_node(pm)
            for plan in p_item.get("plans", []):
                raw_plan_name = plan.get("plan_name", "") or plan.get("name", "") or "Unknown"
                raw_price = plan.get("price")
                if raw_price is None or not isinstance(raw_price, (int, float)):
                    raw_price = 0
                pd_node = PricingDataNode(
                    product=p_item["product"], plan_name=raw_plan_name,
                    price=float(raw_price),
                    billing_cycle=plan.get("billing_cycle", "monthly") or "monthly",
                    features=plan.get("features", []) or [],
                    label=f"{p_item['product']} - {raw_plan_name}",
                    metadata={"task_id": task_id},
                )
                store.create_node(pd_node)
                store.create_edge(GraphEdge(source_id=pm.id, target_id=pd_node.id, edge_type=EdgeType.DERIVED_FROM))
        logger.info("  Pricing: %d models", len(data.get("pricing", [])))
    except Exception as e:
        logger.warning("  Pricing failed: %s", e)

    # ── 3c-4: Market Position ──
    logger.info("3c-4: Market Position...")
    try:
        data = await _llm_json(
            f"Products: {', '.join(products)}\n\n{context[:15000]}\n\n"
            "For EACH product, analyze market position. Return ONLY JSON: "
            '{"positions":[{"product":"X","positioning":"slogan","gtm_strategy":"PLG|sales-led|channel|community","target_audience":"...","key_competitors":["..."]},...]}'
        )
        cnt = 0
        for mp in data.get("positions", []):
            store.create_node(MarketPositionNode(
                product=mp["product"], positioning=mp.get("positioning", ""),
                gtm_strategy=mp.get("gtm_strategy", ""),
                target_audience=mp.get("target_audience", ""),
                label=f"{mp['product']} 市场定位", metadata={"task_id": task_id},
            ))
            cnt += 1
        logger.info("  MarketPosition: %d", cnt)
    except Exception as e:
        logger.warning("  MarketPosition failed: %s", e)

    # ── 3d: SWOT + Scoring + Report ──
    logger.info("3d: SWOT + Scoring + Report...")
    try:
        swot_scoring_prompt = (
            f"Products: {', '.join(products)}\n\n{context[:12000]}\n\n"
            "Generate SWOT, scoring, and report sections in Chinese markdown.\n\n"
            "SWOT RULES:\n"
            "- Generate items based STRICTLY on evidence. Each quadrant should have 2-6 items, "
            "varying NATURALLY across products. DO NOT pad or force equal counts.\n"
            "- If one product has 3 strengths and another has 6, that's OK — reflect reality.\n\n"
            "SCORING RULES:\n"
            "- Score each product on 5 dimensions (0-10). USE THE FULL RANGE.\n"
            "- A 1-point difference is meaningful. Differentiate clearly.\n"
            "- Do NOT cluster all scores around 7-8. Use 4-9 range freely.\n"
            "- Dimensions: 功能丰富度, AI 代码质量, 使用成本, 生态成熟度, 隐私安全 "
            "(adjust to fit the product category).\n\n"
            "Return ONLY JSON: "
            '{"swot":[{"product":"X","strengths":["..."],"weaknesses":["..."],"opportunities":["..."],"threats":["..."]}],'
            '"scoring":[{"product":"X","dimension":"功能","score":8.0,"weight":1.0,"rationale":"简短理由"}],'
            '"report_sections":[{"section":"执行摘要","content":"markdown...","order":0}]}'
        )
        data = await _llm_json(swot_scoring_prompt, max_tokens=8192)
        for sw in data.get("swot", []):
            store.create_node(SWOTNode(
                product=sw["product"], strengths=sw.get("strengths", []),
                weaknesses=sw.get("weaknesses", []), opportunities=sw.get("opportunities", []),
                threats=sw.get("threats", []), label=f"{sw['product']} SWOT",
                metadata={"task_id": task_id},
            ))
        for sc in data.get("scoring", []):
            store.create_node(ScoringNode(
                dimension=sc["dimension"], score=sc["score"], weight=sc.get("weight", 1.0),
                rationale=sc.get("rationale", ""),
                label=f"{sc.get('product', '')} - {sc['dimension']}",
                metadata={"task_id": task_id, "product": sc.get("product", "")},
            ))
        for rs in data.get("report_sections", []):
            store.create_node(ReportSectionNode(
                section=rs["section"], content=rs["content"], order=rs.get("order", 0),
                label=rs["section"], metadata={"task_id": task_id},
            ))
        logger.info("  SWOT:%d Scoring:%d Report:%d", len(data.get("swot", [])),
                     len(data.get("scoring", [])), len(data.get("report_sections", [])))
    except Exception as e:
        logger.warning("  SWOT/Report failed: %s", e)

    # ── 3e: 创建边 (derived_from) ──
    logger.info("3e: 创建知识图谱边...")
    all_nodes = store.query_nodes()
    # 构建 product→source_nodes 映射
    product_sources: dict[str, list] = {}
    for n in source_nodes:
        label = n.label.lower()
        for p in products:
            if p.lower() in label or p.lower() in n.metadata.get("snippet", "").lower():
                product_sources.setdefault(p, []).append(n)
                break

    edge_count = 0
    for node in all_nodes:
        layer = getattr(node, "layer", 0)
        if layer != 2:
            continue
        p = getattr(node, "product", "") or node.metadata.get("product", "")
        if not p:
            continue
        # 连接分析节点到对应产品的 SourceInfo
        sources = product_sources.get(p, [])[:5]
        for src in sources:
            store.create_edge(GraphEdge(
                source_id=node.id, target_id=src.id,
                edge_type=EdgeType.DERIVED_FROM,
            ))
            edge_count += 1
        # 连接分析节点到对应产品的 WebPage
        for wp in page_nodes:
            if p.lower() in wp.title.lower() or p.lower() in (wp.text or "")[:300].lower():
                store.create_edge(GraphEdge(
                    source_id=node.id, target_id=wp.id,
                    edge_type=EdgeType.DERIVED_FROM,
                ))
                edge_count += 1
                if edge_count > 200:
                    break
        if edge_count > 200:
            break

    # L3 → L2 edges
    l2_nodes = [n for n in all_nodes if getattr(n, "layer", 0) == 2]
    for node in all_nodes:
        if getattr(node, "layer", 0) != 3:
            continue
        for l2 in l2_nodes[:10]:
            store.create_edge(GraphEdge(
                source_id=node.id, target_id=l2.id,
                edge_type=EdgeType.DERIVED_FROM,
            ))
            edge_count += 1

    logger.info("  Edges created: %d", edge_count)

    # ── 3f: 写 task_targets.json ──
    tt_path = os.path.join("data", "task_targets.json")
    existing = {}
    if os.path.exists(tt_path):
        try:
            with open(tt_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass
    existing[task_id] = products
    os.makedirs("data", exist_ok=True)
    with open(tt_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    logger.info("  task_targets.json: %s → %s", task_id, products)

    # ── 统计 ──
    lc, nt = {"L1": 0, "L2": 0, "L3": 0}, {}
    for n in all_nodes:
        l = getattr(n, "layer", 0)
        lc[f"L{l}" if l in (1,2,3) else "L?"] = lc.get(f"L{l}" if l in (1,2,3) else "L?", 0) + 1
        t = type(n).__name__
        nt[t] = nt.get(t, 0) + 1

    summary = {"topic": topic["name"], "task_id": task_id, "products": products,
               "kg_nodes": len(all_nodes), "kg_by_layer": lc, "kg_by_type": nt,
               "cache_entries": tool_cache.stats().get("total_entries", 0)}
    with open(f"data/demo_{topic_id}_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info("KG: %d 节点 %s | %s", len(all_nodes), lc, nt)
    return summary


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════


async def main():
    parser = argparse.ArgumentParser(description="Demo 数据预灌")
    parser.add_argument("--topic", type=str, default="collab",
                        choices=["collab", "ai-chat", "short-video", "ai-ide", "all"],
                        help="选题 ID（默认 collab）")
    parser.add_argument("--phase", type=str, default="all",
                        choices=["search", "scrape", "pipeline", "all"],
                        help="执行阶段（默认 all）")
    parser.add_argument("--stats", action="store_true", help="只看缓存统计")
    args = parser.parse_args()

    # 确保 bypass 模式以写入缓存
    os.environ["TOOL_CACHE_MODE"] = "bypass"

    if args.stats:
        stats = tool_cache.stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return

    topics_to_run = list(TOPICS.keys()) if args.topic == "all" else [args.topic]

    for tid in topics_to_run:
        logger.info("")
        logger.info("█" * 60)
        logger.info("█ Topic: %s", TOPICS[tid]["name"])
        logger.info("█" * 60)

        if args.phase in ("search", "all"):
            await phase_search(tid)

        if args.phase in ("scrape", "all"):
            await phase_scrape(tid)

        if args.phase in ("pipeline", "all"):
            await phase_pipeline(tid)

    # 最终缓存统计
    stats = tool_cache.stats()
    logger.info("")
    logger.info("全部完成！缓存统计: %s", json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
