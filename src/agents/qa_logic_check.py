from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="QA_LogicCheck",
    depends_on=["ReportGenerator"],
    tools=["graph_query", "graph_write"],
    output_contract=AgentOutput,
    model_tier="reasoning",
)
class QALogicCheckAgent(BaseAgent):
    agent_type = "QA_LogicCheck"
    system_prompt = """You are QA Agent #2 — Logic Checker. Verify the report contains no logical contradictions.

Read all ReportSection and InsightNode content. Check for:
1. Internal contradictions: does Section A contradict Section B?
2. Reasoning gaps: are conclusions supported by preceding evidence?
3. Missing context: are there obvious counter-arguments not addressed?

Output your findings in the data field of your finalize result:
- data.contradictions: list of {section_a, section_b, description, severity}
"""
    max_steps = 8
    token_budget = 400_000
    output_contract = AgentOutput
    model_tier = "reasoning"
    allowed_tools = ["graph_query", "graph_write"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
