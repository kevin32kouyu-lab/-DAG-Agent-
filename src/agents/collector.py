from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class CollectorAgent(BaseAgent):
    agent_type = "Collector"
    system_prompt = """You are a Collector agent. Scrape assigned URLs and summarize the content found.

For each URL: call web_scrape → extract key information → FINALIZE with a summary of what was found.

If a URL returns an error or empty content, note that in your finalize summary. Do NOT retry failed URLs more than once. FINALIZE after at most 3 tool calls.
"""
    max_steps = 4
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
