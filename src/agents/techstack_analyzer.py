from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class TechStackAnalyzer(BaseAgent):
    agent_type = "TechStackAnalyzer"
    system_prompt = """You are a Tech Stack Analyzer for competitive analysis.

Infer technology stack from available clues (job postings, engineering blogs,
open-source repos, HTTP headers):
1. Identify likely languages and frameworks
2. Identify infrastructure choices (cloud, database, CDN)
3. Assign confidence to each inference

Output: TechStackNode per product.
"""
    max_steps = 10
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
