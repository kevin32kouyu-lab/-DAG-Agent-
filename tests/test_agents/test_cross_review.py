from src.agents.cross_review import CrossReviewAgent


def test_cross_review_system_prompt_includes_contradicts_edges():
    """CrossReview agent system prompt should instruct creating contradicts edges."""
    prompt = CrossReviewAgent.system_prompt
    assert "contradicts" in prompt.lower()
    assert "edge" in prompt.lower()
