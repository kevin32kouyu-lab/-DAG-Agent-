"""DAG 编译器：把用户输入和工作流模板转换为可执行 TaskDAG。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.dag.models import DAGNode, TaskDAG
from src.dag.templates import WorkflowScenario, WorkflowTemplateRegistry, get_default_template_registry


SCENARIO_TO_TEMPLATE_ID = {
    WorkflowScenario.SAAS.value: "saas_competitor_analysis",
    WorkflowScenario.APP.value: "app_competitor_analysis",
}


@dataclass(frozen=True)
class WorkflowCompileRequest:
    """编译 DAG 所需的最小请求信息。"""

    task_id: str
    targets: list[str]
    scenario: str = WorkflowScenario.SAAS.value
    collection_depth: str = "standard"
    schema: dict[str, Any] = field(default_factory=dict)


class WorkflowCompiler:
    """把模板编译成具体任务 DAG。"""

    def __init__(self, registry: WorkflowTemplateRegistry | None = None):
        self.registry = registry or get_default_template_registry()

    def compile(self, request: WorkflowCompileRequest) -> TaskDAG:
        targets = [target.strip() for target in request.targets if target and target.strip()]
        if not targets:
            raise ValueError("targets must contain at least one product")

        scenario = request.scenario.lower().strip()
        template_id = SCENARIO_TO_TEMPLATE_ID.get(scenario)
        if not template_id:
            raise ValueError(f"unsupported scenario: {request.scenario}")

        template = self.registry.get(template_id)
        nodes: list[DAGNode] = []

        for spec in template.nodes:
            input_query = {
                "targets": targets,
                "scenario": scenario,
                "stage": spec.stage,
                "role_group": spec.role_group,
                "collection_depth": request.collection_depth,
                "schema": request.schema,
                **spec.input_defaults,
            }
            nodes.append(DAGNode(
                node_id=spec.node_id,
                agent_type=spec.agent_type,
                input_query=input_query,
                depends_on=list(spec.depends_on),
                priority=spec.priority,
                max_retries=spec.max_retries,
                stage=spec.stage,
                role_group=spec.role_group,
                display_name=spec.display_name,
                description=spec.description,
                output_contract=spec.output_contract,
                degradation_policy=dict(spec.degradation_policy),
                source_policy=dict(spec.source_policy),
                context={
                    "workflow_template_id": template.template_id,
                    "workflow_template_name": template.name,
                    "scenario": scenario,
                },
            ))

        return TaskDAG(
            task_id=request.task_id,
            nodes=nodes,
            workflow_template_id=template.template_id,
            scenario=scenario,
            targets=targets,
            metadata={
                "planning_mode": "template",
                "workflow_template_name": template.name,
                "collection_depth": request.collection_depth,
                "template_description": template.description,
            },
        )
