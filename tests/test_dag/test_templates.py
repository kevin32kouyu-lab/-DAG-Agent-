import pytest

from src.dag.templates import WorkflowScenario, get_default_template_registry


def test_default_registry_contains_saas_and_app_templates():
    registry = get_default_template_registry()

    assert registry.get("saas_competitor_analysis").scenario == WorkflowScenario.SAAS
    assert registry.get("app_competitor_analysis").scenario == WorkflowScenario.APP


def test_saas_template_has_required_pipeline_nodes():
    template = get_default_template_registry().get("saas_competitor_analysis")
    node_ids = {node.node_id for node in template.nodes}

    assert "source_discovery" in node_ids
    assert "collector" in node_ids
    assert "data_enricher" in node_ids
    assert "feature_analysis" in node_ids
    assert "pricing_analysis" in node_ids
    assert "sentiment_analysis" in node_ids
    assert "market_position" in node_ids
    assert "cross_review" in node_ids
    assert "swot" in node_ids
    assert "report" in node_ids
    assert "qa_fact_check" in node_ids
    assert "qa_logic_check" in node_ids


def test_template_dependencies_reference_existing_nodes():
    registry = get_default_template_registry()

    for template_id in registry.template_ids():
        template = registry.get(template_id)
        node_ids = {node.node_id for node in template.nodes}
        for node in template.nodes:
            assert set(node.depends_on).issubset(node_ids), node.node_id


def test_registry_raises_for_unknown_template():
    registry = get_default_template_registry()

    with pytest.raises(KeyError, match="unknown_template"):
        registry.get("unknown_template")
