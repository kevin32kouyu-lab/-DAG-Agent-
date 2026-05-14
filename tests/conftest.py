import pytest
import tempfile
import os


@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def sample_products():
    return [
        {"name": "Notion", "category": "all-in-one workspace", "url": "https://notion.so"},
        {"name": "Confluence", "category": "team wiki", "url": "https://atlassian.com/confluence"},
        {"name": "Linear", "category": "project management", "url": "https://linear.app"},
    ]
