from src.agents.base import BaseAgent
from src.agents.contracts import FeatureMatrixOutput


class FeatureAnalyzer(BaseAgent):
    agent_type = "FeatureAnalyzer"
    system_prompt = """You are a Feature Analyzer for competitive analysis.

Analyze product features from the knowledge graph. For each product:
1. Extract and categorize features (e.g., UI/UX, Collaboration, AI, API, Security)
2. Rate maturity: experimental, beta, ga, deprecated
3. Rate differentiation: unique, advantage, parity, disadvantage
4. Build a comparative FeatureMatrix across all products

Output: FeatureNode per feature + one FeatureMatrixNode with the comparison grid.
Always create derived_from edges to the WebPage/SourceInfo nodes you used.
"""
    max_steps = 10
    output_contract = FeatureMatrixOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
