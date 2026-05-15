"""Record a pipeline run to generate the replay fixture at agent-output level.

Usage: python -m tests.test_integration.record_fixture
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.llm_gateway.gateway import LLMGateway
from src.knowledge_graph.store import GraphStore
from src.agents.orchestrator import OrchestratorAgent
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.tools.web_tools import WebScrapeTool, WebSearchTool
from src.dag.scheduler import DAGScheduler
from src.dag.executor import AgentExecutor
from src.dag.models import NodeState


class RecordingAgentExecutor(AgentExecutor):
    """Executor that records each agent's output after execution.

    Only keeps the LAST execution per node_id (successful retries overwrite failures).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.recorded_outputs: dict[str, dict] = {}

    async def execute(self, node):
        try:
            await super().execute(node)
            output_data = node.context.get("_output_data", {})

            serialized_data = {}
            if isinstance(output_data, dict):
                for k, v in output_data.items():
                    if hasattr(v, 'model_dump'):
                        serialized_data[k] = v.model_dump()
                    elif hasattr(v, 'dict'):
                        serialized_data[k] = v.dict()
                    else:
                        serialized_data[k] = v

            self.recorded_outputs[node.node_id] = {
                "node_id": node.node_id,
                "agent_type": node.agent_type,
                "output": {
                    "agent_type": node.agent_type,
                    "node_id": node.node_id,
                    "summary": f"{node.agent_type} completed",
                    "confidence": 0.8,
                    "data": serialized_data,
                    "nodes_created": [],
                    "edges_created": [],
                    "status": "completed",
                },
                "traces": [],
            }
        except Exception as e:
            # Only record failure if we haven't recorded success yet (for retries)
            if node.node_id not in self.recorded_outputs:
                self.recorded_outputs[node.node_id] = {
                    "node_id": node.node_id,
                    "agent_type": node.agent_type,
                    "output": {
                        "agent_type": node.agent_type,
                        "node_id": node.node_id,
                        "summary": str(e),
                        "confidence": 0.0,
                        "data": {},
                        "nodes_created": [],
                        "edges_created": [],
                        "status": "failed",
                    },
                    "traces": [],
                }
            raise

    def get_outputs_list(self) -> list[dict]:
        return list(self.recorded_outputs.values())


async def main():
    fixture_path = Path(__file__).parent / "fixtures" / "pipeline_smoke.json"

    real_gw = LLMGateway(
        default_model="deepseek-chat",
        model_map={
            "reasoning": "deepseek-chat",
            "analysis": "deepseek-chat",
            "batch": "deepseek-chat",
        },
        provider_map={"deepseek-chat": "openai_compatible"},
    )

    db_path = str(Path(__file__).parent / "fixtures" / "_record_temp.db")
    store = GraphStore(db_path=db_path)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    tools.register(WebScrapeTool)
    tools.register(WebSearchTool)

    task_id = "smoke-rec-1"
    # Minimal config: 1 product, only 2 analysis dimensions to keep DAG small
    schema = {
        "targets": ["Notion"],
        "industry": "saas",
        "collection_depth": "shallow",
        "execution_mode": "auto",
        "dimensions": ["features", "sentiment"],
        "exclude_dimensions": ["pricing", "techstack", "market_position", "swot"],
    }

    print("Generating DAG via Orchestrator...")
    orch = OrchestratorAgent(gateway=real_gw, store=store, tool_registry=tools)
    dag, _ = await orch.execute({
        "task_id": task_id,
        "targets": ["Notion"],
        "schema": schema,
    })

    if dag is None:
        print("ERROR: Orchestrator failed to generate DAG")
        return 1

    print(f"DAG generated: {len(dag.nodes)} nodes")
    for node in dag.nodes:
        print(f"  - {node.node_id}: {node.agent_type}")
        node.context["task_id"] = task_id

    scheduler = DAGScheduler()
    executor = RecordingAgentExecutor(gateway=real_gw, store=store, tool_registry=tools)

    print("Running pipeline...")
    await scheduler.run(dag, executor, gateway=real_gw)

    failed = [n for n in dag.nodes if n.state == NodeState.FAILED]
    completed = [n for n in dag.nodes if n.state == NodeState.COMPLETED]
    print(f"\nResults: {len(completed)} completed, {len(failed)} failed")
    for node in dag.nodes:
        print(f"  {node.node_id}: {node.state.value}")

    # Build fixture: DAG structure + agent outputs
    fixture = {
        "dag": {
            "task_id": dag.task_id,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "agent_type": n.agent_type,
                    "input_query": n.input_query,
                    "depends_on": n.depends_on,
                    "priority": n.priority,
                }
                for n in dag.nodes
            ],
        },
        "outputs": executor.get_outputs_list(),
    }

    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    with open(fixture_path, "w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2, ensure_ascii=False)

    print(f"\nRecorded {len(executor.recorded_outputs)} agent outputs to {fixture_path}")

    # Check for Writer output
    writer_nodes = [n for n in dag.nodes if n.agent_type == "ReportGenerator"]
    if writer_nodes and writer_nodes[0].state == NodeState.COMPLETED:
        output = writer_nodes[0].context.get("_output_data", {})
        report = output.get("report_markdown", "")
        if report:
            print(f"Report generated: {len(report)} chars")
        else:
            print("WARNING: Writer completed but no report_markdown found")
    elif writer_nodes:
        print("WARNING: Writer did not complete successfully")

    # Cleanup temp db
    try:
        os.unlink(db_path)
    except (OSError, PermissionError):
        pass

    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
