import pytest
import tempfile
import os


REAL_LLM_TEST_FILES = {
    "test_live_deepseek.py",
    "test_diagnose_analyzers.py",
    "test_pipeline_smoke.py",
    "test_writer_real.py",
}


def _real_llm_enabled(env: dict[str, str] | None = None) -> bool:
    """判断是否显式允许真实 LLM 测试。"""
    source = env if env is not None else os.environ
    return str(source.get("RUN_REAL_LLM_TESTS", "")).lower() in {"1", "true", "yes"}


def _is_real_llm_test(path: str, markers: set[str]) -> bool:
    """根据文件名和标记识别真实 LLM 测试。"""
    filename = os.path.basename(path)
    return filename in REAL_LLM_TEST_FILES or bool(markers & {"real_llm", "smoke"})


def pytest_collection_modifyitems(config, items):
    """默认跳过真实 LLM 测试，避免本地全量测试卡住或产生费用。"""
    if _real_llm_enabled():
        return

    skip_real_llm = pytest.mark.skip(reason="真实 LLM 测试默认跳过；设置 RUN_REAL_LLM_TESTS=1 后运行")
    for item in items:
        markers = {marker.name for marker in item.iter_markers()}
        if _is_real_llm_test(str(item.path), markers):
            item.add_marker(skip_real_llm)


@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    try:
        os.unlink(path)
    except PermissionError:
        pass


@pytest.fixture
def sample_products():
    return [
        {"name": "Notion", "category": "all-in-one workspace", "url": "https://notion.so"},
        {"name": "Confluence", "category": "team wiki", "url": "https://atlassian.com/confluence"},
        {"name": "Linear", "category": "project management", "url": "https://linear.app"},
    ]
