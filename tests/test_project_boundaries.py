"""测试项目文件边界，避免运行数据和代码混在一起。"""

from pathlib import Path


def test_gitignore_excludes_runtime_data_files():
    content = Path(".gitignore").read_text(encoding="utf-8")

    required_patterns = [
        "data/*.db",
        "data/*.db-wal",
        "data/*.db-shm",
        "data/task_targets.json",
    ]

    for pattern in required_patterns:
        assert pattern in content


def test_tests_readme_documents_test_boundaries():
    content = Path("tests/README.md").read_text(encoding="utf-8")

    assert ".venv\\Scripts\\python.exe -m pytest tests -q" in content
    assert "RUN_REAL_LLM_TESTS=1" in content
    assert "npm run test" in content


def test_docs_readme_points_to_current_and_historical_docs():
    content = Path("docs/README.md").read_text(encoding="utf-8")

    assert "README.md" in content
    assert "ARCHITECTURE.md" in content
    assert "CONTEXT.md" in content
    assert "docs/superpowers/plans/" in content
    assert "docs/superpowers/specs/" in content


def test_frontend_routes_are_lazy_loaded():
    content = Path("web/src/App.tsx").read_text(encoding="utf-8")

    assert "lazy(() => import('./pages/TaskPanel'))" in content
    assert "lazy(() => import('./pages/Monitor'))" in content
    assert "lazy(() => import('./pages/Report'))" in content
    assert "lazy(() => import('./pages/TraceExplorer'))" in content


def test_report_page_lazy_loads_analytics_dashboard():
    content = Path("web/src/pages/Report.tsx").read_text(encoding="utf-8")

    assert "lazy(() => import('../components/charts/AnalyticsDashboard'))" in content
    assert "import AnalyticsDashboard from '../components/charts/AnalyticsDashboard'" not in content


def test_frontend_pdf_export_uses_backend_endpoint():
    content = Path("web/src/utils/export.ts").read_text(encoding="utf-8")
    package_json = Path("web/package.json").read_text(encoding="utf-8")
    package_lock = Path("web/package-lock.json").read_text(encoding="utf-8")

    assert "/api/report/${encodeURIComponent(taskId)}?format=pdf" in content
    assert "html2pdf.js" not in content
    assert "html2pdf.js" not in package_json
    assert "html2pdf.js" not in package_lock
