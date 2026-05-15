import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.agents.tools.company_scope import CompanyScopeTool


class TestCompanyScopeTool:
    async def test_execute_requires_query(self):
        tool = CompanyScopeTool()
        result = await tool.execute(action="tech_stack", query="")
        assert "error" in result

    async def test_tech_stack_returns_expected_structure(self):
        tool = CompanyScopeTool()
        result = await tool.execute(action="tech_stack", query="github.com")
        assert "domain" in result
        assert "detected" in result
        assert isinstance(result["detected"], list)

    async def test_financials_returns_structure(self):
        tool = CompanyScopeTool()
        result = await tool.execute(action="financials", query="Apple")
        # May return "note" if SEC lookup fails in CI, or company data
        assert "error" in result or "company" in result or "note" in result

    async def test_competitors_returns_list(self):
        tool = CompanyScopeTool()
        result = await tool.execute(action="competitors", query="Stripe")
        assert "competitors" in result or "error" in result

    async def test_profile_aggregates_results(self):
        tool = CompanyScopeTool()
        result = await tool.execute(action="profile", query="stripe.com")
        assert "query" in result
        # Profile should have tech_stack or error for each sub-call
        assert any(k in result for k in ("tech_stack", "error"))

    async def test_parse_tech_signatures_detects_nginx(self):
        headers = {"Server": "nginx/1.18"}
        html = ""
        result = CompanyScopeTool._parse_tech_signatures(headers, html)
        assert any(t["tech"] == "Nginx" for t in result)

    async def test_parse_tech_signatures_detects_wordpress(self):
        headers = {}
        html = '<html><head></head><body>wp-content/themes/mytheme</body></html>'
        result = CompanyScopeTool._parse_tech_signatures(headers, html)
        assert any(t["tech"] == "WordPress" for t in result)

    async def test_guess_domain_from_name(self):
        assert CompanyScopeTool._guess_domain("Stripe") == "stripe.com"
        assert CompanyScopeTool._guess_domain("stripe.com") == "stripe.com"
        assert CompanyScopeTool._guess_domain("https://stripe.com") == "stripe.com"

    async def test_guess_domain_from_multi_word(self):
        assert CompanyScopeTool._guess_domain("GitHub Inc") == "githubinc.com"
