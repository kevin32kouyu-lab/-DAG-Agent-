import json
from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry
from src.dag.models import TaskDAG, DAGNode


@agent_registry.register(
    agent_type="Orchestrator",
    depends_on=[],
    tools=[],
    output_contract=AgentOutput,
    model_tier="reasoning",
)
class OrchestratorAgent(BaseAgent):
    agent_type = "Orchestrator"
    model_tier = "reasoning"
    allowed_tools = []
    system_prompt = """You are the Orchestrator for a competitive analysis multi-agent system.

Your job: given target products and analysis schema, generate a DAG (directed acyclic graph) of agent tasks.

Available agent types and their dependencies:
- SourceDiscovery: no dependencies, single instance per task
- Collector: depends_on [SourceDiscovery], one per URL group
- DataEnricher: depends_on [Collector, ...], single instance
- FeatureAnalyzer: depends_on [DataEnricher]
- SentimentAnalyzer: depends_on [DataEnricher]
- PricingAnalyst: depends_on [DataEnricher]
- TechStackAnalyzer: depends_on [DataEnricher]
- MarketPositionAnalyzer: depends_on [DataEnricher]
- CrossReviewAgent: depends_on [FeatureAnalyzer, SentimentAnalyzer, PricingAnalyst, TechStackAnalyzer, MarketPositionAnalyzer]
- SWOTAnalyzer: depends_on [CrossReviewAgent] (or analysis agents if no cross-review)
- Writer: depends_on [SWOTAnalyzer]
- QA_FactCheck: depends_on [Writer]
- QA_LogicCheck: depends_on [Writer]

Output ONLY valid JSON in this exact structure:
{
  "task_id": "...",
  "targets": [...],
  "nodes": [
    {"node_id": "...", "agent_type": "...", "depends_on": [...], "input_query": {...}, "priority": 0}
  ]
}

Rules:
- node_id must be unique
- depends_on must list node_ids that MUST complete before this node starts
- input_query should contain {"node_type": "..."} or {"product": "...", ...} as appropriate
- Assign priority 0 (normal) or 1 (high)
- SourceDiscovery is always the first node with no dependencies
- Collectors should be per-product (one for each target's official website) plus shared ones (G2, ProductHunt, News)
- Skip dimensions excluded in schema.exclude_dimensions
"""

    max_steps = 5
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple[TaskDAG | None, list]:
        self.context.init(task)
        targets = task.get("targets", [])
        schema = task.get("schema", {"industry": "saas"})
        dag_json = await self._generate_dag(targets, schema)
        if dag_json is None:
            return None, []
        dag = self._json_to_dag(dag_json)
        return dag, []

    async def _generate_dag(self, targets: list[str], schema: dict) -> dict | None:
        prompt = f"""Generate a DAG for competitive analysis of: {targets}
Schema: {json.dumps(schema, default=str)}
Dimensions to include (from schema.dimensions or saas defaults):
  - FeatureAnalyzer, SentimentAnalyzer, PricingAnalyst, TechStackAnalyzer, MarketPositionAnalyzer
Excluded dimensions: {schema.get('exclude_dimensions', [])}
"""
        resp = await self.gateway.chat(
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
            model_tier=self.model_tier,
            max_tokens=4096,
        )
        try:
            return json.loads(resp.content)
        except json.JSONDecodeError:
            return None

    def _json_to_dag(self, dag_json: dict) -> TaskDAG:
        nodes = [
            DAGNode(
                node_id=n["node_id"],
                agent_type=n["agent_type"],
                input_query=n.get("input_query", {}),
                depends_on=n.get("depends_on", []),
                priority=n.get("priority", 0),
            )
            for n in dag_json.get("nodes", [])
        ]
        return TaskDAG(task_id=dag_json.get("task_id", ""), nodes=nodes)
