"""测试真实 LLM 测试不会进入默认本地测试路径。"""

from tests.conftest import _is_real_llm_test, _real_llm_enabled


def test_real_llm_tests_are_disabled_by_default():
    assert _real_llm_enabled({}) is False


def test_real_llm_tests_can_be_enabled_explicitly():
    assert _real_llm_enabled({"RUN_REAL_LLM_TESTS": "1"}) is True


def test_real_llm_paths_are_detected():
    assert _is_real_llm_test("tests/test_agents/test_live_deepseek.py", set()) is True
    assert _is_real_llm_test("tests/test_integration/test_writer_real.py", set()) is True
    assert _is_real_llm_test("tests/test_agents/test_component.py", set()) is False
    assert _is_real_llm_test("tests/test_any.py", {"real_llm"}) is True
