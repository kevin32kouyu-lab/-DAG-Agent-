from src.agents.base import BaseAgent
from src.agents.contracts import ReportOutput


class WriterAgent(BaseAgent):
    agent_type = "Writer"
    system_prompt = """You are a Report Writer agent. Generate a structured competitive analysis report.

Read all Layer 2 and Layer 3 nodes. Produce a markdown report with sections:
1. Executive Summary
2. Feature Comparison Matrix
3. Pricing Analysis
4. User Sentiment Analysis
5. Technical Capabilities
6. Market Position
7. SWOT Analysis (per product)
8. Strategic Recommendations

Each claim should reference source data. Create ReportSection nodes for each section.
"""
    max_steps = 15
    output_contract = ReportOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
