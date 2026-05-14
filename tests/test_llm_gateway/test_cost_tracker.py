from src.llm_gateway.cost_tracker import CostTracker


def test_cost_tracker_initial_summary():
    ct = CostTracker()
    s = ct.summary()
    assert s["total_tokens"] == 0
    assert s["total_cost"] == 0.0
    assert s["total_calls"] == 0
    assert s["per_agent"] == {}


def test_cost_tracker_single_record():
    ct = CostTracker()
    ct.record("FeatureAnalyzer", 1000, 0.05)
    s = ct.summary()
    assert s["total_tokens"] == 1000
    assert s["total_cost"] == 0.05
    assert s["total_calls"] == 1
    assert s["per_agent"]["FeatureAnalyzer"]["tokens"] == 1000
    assert s["per_agent"]["FeatureAnalyzer"]["cost"] == 0.05
    assert s["per_agent"]["FeatureAnalyzer"]["calls"] == 1


def test_cost_tracker_multiple_agents():
    ct = CostTracker()
    ct.record("FeatureAnalyzer", 500, 0.02)
    ct.record("PricingAnalyst", 300, 0.01)
    ct.record("FeatureAnalyzer", 200, 0.01)
    s = ct.summary()
    assert s["total_tokens"] == 1000
    assert s["total_calls"] == 3
    assert s["per_agent"]["FeatureAnalyzer"]["tokens"] == 700
    assert s["per_agent"]["FeatureAnalyzer"]["cost"] == 0.03
    assert s["per_agent"]["PricingAnalyst"]["tokens"] == 300
    assert s["per_agent"]["PricingAnalyst"]["cost"] == 0.01


def test_cost_tracker_float_rounding():
    ct = CostTracker()
    ct.record("Test", 100, 0.0001)
    ct.record("Test", 100, 0.0002)
    s = ct.summary()
    assert s["total_cost"] == 0.0003


def test_cost_tracker_per_agent_calls_count():
    ct = CostTracker()
    ct.record("A1", 10, 0.001)
    ct.record("A1", 20, 0.002)
    ct.record("A2", 30, 0.003)
    assert ct.per_agent["A1"]["calls"] == 2
    assert ct.per_agent["A2"]["calls"] == 1
