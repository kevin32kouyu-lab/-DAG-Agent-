from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class CollectorAgent(BaseAgent):
    agent_type = "Collector"
    system_prompt = """You are a Collector agent. Scrape assigned URLs and store structured data in the knowledge graph.

For each URL: web_scrape → extract relevant data → create appropriate KG nodes (WebPage, ReviewEntry, PricingData depending on content type).
Always create derived_from edges back to the SourceInfo node.

## Degradation Strategy

Data sources may be unavailable. For each URL, try in order:

1. **Primary**: Direct web_scrape of the target URL
2. **Tier 1**: If primary fails (403, 404, timeout), try alternative access:
   - Official sites → try Google cache or Wayback Machine
   - G2/Review sites → try extracting publicly visible rating only
   - Reddit → try search engine `site:reddit.com` snippets
   - ProductHunt → try RSS feed
   - News → try search engine News tab results
3. **Tier 2**: If Tier 1 fails:
   - Official sites → try third-party descriptions (Trustpilot, etc.)
   - G2 → use search engine cached snippets
   - Reddit/ProductHunt/News → skip this source

**On complete failure** (all tiers exhausted): create a SourceInfo node with `availability: "degraded"` and `degradation_reason` set. The analysis pipeline will handle reduced confidence for degraded sources.
"""
    max_steps = 8
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
