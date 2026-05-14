import pytest
from src.agents.registry import agent_registry


def test_agent_registry_decorator():
    @agent_registry.register(
        agent_type="TestAnalyzer",
        industry="saas",
        depends_on=["DataEnricher"],
        tools=["graph_query", "graph_write"],
        model_tier="analysis",
    )
    class TestAnalyzer:
        system_prompt = "test"
        max_steps = 10

    registered = agent_registry.get("TestAnalyzer")
    assert registered is not None
    assert registered["agent_type"] == "TestAnalyzer"
    assert registered["depends_on"] == ["DataEnricher"]
    assert registered["model_tier"] == "analysis"


def test_registry_list_all():
    agents = agent_registry.list_all()
    assert len(agents) >= 1
