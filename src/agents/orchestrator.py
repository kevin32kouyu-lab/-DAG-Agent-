"""这个模块负责把用户的竞品分析任务规划成可执行 DAG。"""

import json
import logging
from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry
from src.dag.models import TaskDAG, DAGNode

logger = logging.getLogger(__name__)


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
- ReportGenerator: depends_on [SWOTAnalyzer]
- QA_FactCheck: depends_on [ReportGenerator]
- QA_LogicCheck: depends_on [ReportGenerator]

Available data source tools (agents have access to these):
- tavily_search: AI-powered web search (1000 free/month)
- github: Repository stats, releases, contributors (5000 req/h with token)
- hackernews: Developer community discussions
- reddit: User sentiment and community feedback
- google_news: Recent news coverage (RSS)
- company_scope: Tech stack detection, SEC financials, domain intel, social presence
- app_store: iOS App Store & Google Play ratings, reviews, update frequency
- producthunt: Launch heat, community upvotes, product tagline
- wayback_machine: Website history, redesign cadence, feature launch timeline
- google_trends: Search interest comparison across products
- social_media: Chinese platforms (小红书/知乎/微博) brand mentions
- tianyancha: Chinese company registration data (paid, requires token)
- web_search / web_scrape: General web data collection

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
- Collectors should be per-product (one for each target's official website) plus shared ones (G2, ProductHunt, HackerNews, GitHub, GoogleNews, Reddit)
- For Chinese market targets, also query 天眼查 (Tianyancha) for company registration data when a TIANYANCHA_TOKEN is available
- Skip dimensions excluded in schema.exclude_dimensions (analysis agents only)
- **ReportGenerator, QA_FactCheck, QA_LogicCheck are ALWAYS required** — never skip them, even if exclude_dimensions lists their upstream
- SWOTAnalyzer is required unless "swot" is in exclude_dimensions
- The final DAG must always end with: SWOTAnalyzer (or last analysis) → ReportGenerator → QA_FactCheck → QA_LogicCheck
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
        dag_json = self._ensure_mandatory_nodes(dag_json, schema, targets)
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
            temperature=0.1,
            skip_cache=True,
        )
        parsed = self._parse_dag_json(resp.content)
        if parsed is None:
            preview = resp.content[:200].replace("\n", " ")
            logger.warning("DAG 生成结果无法解析，已返回空结果：%s", preview)
        return parsed

    @staticmethod
    def _parse_dag_json(text: str) -> dict | None:
        import re
        content = text.strip()

        # 1) Raw parse (most LLMs return clean JSON for DAG generation)
        try:
            d = json.loads(content)
            if isinstance(d, dict) and "nodes" in d:
                return d
        except json.JSONDecodeError:
            pass

        # 2) Strip markdown code fences
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*\n?", "", content)
            content = re.sub(r"\n?```\s*$", "", content)
            try:
                d = json.loads(content)
                if isinstance(d, dict) and "nodes" in d:
                    return d
            except json.JSONDecodeError:
                pass

        # 3) Fallback: use _extract_json but prefer "nodes" key
        from src.agents.base import BaseAgent
        result = BaseAgent._extract_json(text)
        if isinstance(result, dict) and "nodes" in result:
            return result

        return None

    # Agent types that MUST exist in every DAG regardless of exclude_dimensions.
    MANDATORY_AGENTS = ["ReportGenerator", "QA_FactCheck", "QA_LogicCheck"]
    # The final analysis node that ReportGenerator should depend on if SWOT is absent.
    FALLBACK_REPORT_DEP = "FeatureAnalyzer"

    @staticmethod
    def _valid_node_dicts(raw_nodes: object) -> list[dict]:
        """过滤 LLM 返回的坏节点，并补齐 DAGNode 需要的默认字段。"""
        if not isinstance(raw_nodes, list):
            logger.warning("DAG 节点跳过：nodes 字段不是列表")
            return []

        validated = []
        for i, n in enumerate(raw_nodes):
            if not isinstance(n, dict):
                logger.warning("DAG 节点跳过：第 %s 个节点不是对象", i)
                continue
            if "node_id" not in n or "agent_type" not in n:
                logger.warning("DAG 节点跳过：第 %s 个节点缺少 node_id 或 agent_type", i)
                continue
            n = dict(n)
            n.setdefault("input_query", {})
            n.setdefault("depends_on", [])
            n.setdefault("priority", 0)
            validated.append(n)
        return validated

    def _json_to_dag(self, dag_json: dict) -> TaskDAG:
        raw_nodes = dag_json.get("nodes", [])
        validated = self._valid_node_dicts(raw_nodes)
        if not validated and raw_nodes:
            raise ValueError(f"All {len(raw_nodes)} nodes from LLM are missing node_id/agent_type")
        nodes = [
            DAGNode(
                node_id=n["node_id"],
                agent_type=n["agent_type"],
                input_query=n.get("input_query", {}),
                depends_on=n.get("depends_on", []),
                priority=n.get("priority", 0),
            )
            for n in validated
        ]
        return TaskDAG(task_id=dag_json.get("task_id", ""), nodes=nodes)

    def _ensure_mandatory_nodes(self, dag_json: dict, schema: dict,
                                targets: list[str] | None = None) -> dict:
        """补齐报告和 QA 等强制节点，LLM 坏节点会先过滤。"""
        raw_nodes = dag_json.get("nodes", [])
        nodes = self._valid_node_dicts(raw_nodes)
        if not nodes and raw_nodes:
            raise ValueError(f"All {len(raw_nodes)} nodes from LLM are missing node_id/agent_type")
        dag_json["nodes"] = nodes
        existing_types = {n["agent_type"] for n in nodes}
        existing_ids = {n["node_id"] for n in nodes}
        exclude = set(schema.get("exclude_dimensions", []))
        targets = targets or []

        def _unique_id(base: str) -> str:
            cand = base
            i = 1
            while cand in existing_ids:
                cand = f"{base}_{i}"
                i += 1
            existing_ids.add(cand)
            return cand

        # SWOTAnalyzer: required unless explicitly excluded
        if "SWOTAnalyzer" not in existing_types and "swot" not in exclude:
            swot_deps = [n["node_id"] for n in nodes if n["agent_type"] == "CrossReviewAgent"]
            if not swot_deps:
                # No cross-review → depend on last analysis agent
                analysis_order = ["FeatureAnalyzer", "SentimentAnalyzer",
                                  "PricingAnalyst", "TechStackAnalyzer",
                                  "MarketPositionAnalyzer"]
                for at in reversed(analysis_order):
                    swot_deps = [n["node_id"] for n in nodes if n["agent_type"] == at]
                    if swot_deps:
                        break
                if not swot_deps:
                    swot_deps = [n["node_id"] for n in nodes
                                 if n["agent_type"] == "DataEnricher"]
            nodes.append({
                "node_id": _unique_id("swot"),
                "agent_type": "SWOTAnalyzer",
                "depends_on": swot_deps,
                "input_query": {},
                "priority": 0,
                "auto_generated": True,
            })
            existing_types.add("SWOTAnalyzer")

        # ReportGenerator: always required
        if "ReportGenerator" not in existing_types:
            writer_dep = [n["node_id"] for n in nodes
                          if n["agent_type"] == "SWOTAnalyzer"]
            if not writer_dep:
                # SWOT excluded or missing → depend on last available analysis node
                analysis_order = ["FeatureAnalyzer", "SentimentAnalyzer",
                                  "PricingAnalyst", "TechStackAnalyzer",
                                  "MarketPositionAnalyzer", "DataEnricher",
                                  "Collector"]
                for at in analysis_order:
                    writer_dep = [n["node_id"] for n in nodes
                                  if n["agent_type"] == at]
                    if writer_dep:
                        break
            nodes.append({
                "node_id": _unique_id("report_generator"),
                "agent_type": "ReportGenerator",
                "depends_on": writer_dep,
                "input_query": {"targets": targets},
                "priority": 0,
                "auto_generated": True,
            })
            existing_types.add("ReportGenerator")

        # QA agents: always required, depend on ReportGenerator
        writer_node = next((n for n in nodes if n["agent_type"] == "ReportGenerator"), None)
        if writer_node is None:
            raise RuntimeError("ReportGenerator node missing after mandatory injection")
        writer_id = writer_node["node_id"]
        for qa_type in ["QA_FactCheck", "QA_LogicCheck"]:
            if qa_type not in existing_types:
                nodes.append({
                    "node_id": _unique_id(qa_type.lower()),
                    "agent_type": qa_type,
                    "depends_on": [writer_id],
                    "input_query": {},
                    "priority": 0,
                    "auto_generated": True,
                })
                existing_types.add(qa_type)

        dag_json["nodes"] = nodes
        return dag_json
