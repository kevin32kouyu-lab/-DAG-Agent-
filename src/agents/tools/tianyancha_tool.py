"""
天眼查开放平台 API 工具 — 企业工商信息查询

重要: 天眼查 API 是付费服务, 没有真正的免费额度。
  - 企业基本信息: ¥0.15/次
  - 股东信息: ¥0.15/次
  - 司法风险: ¥1.50/次
  - 工商信息组合: ¥1.00/次
  - 搜索接口: 按次计费

申请步骤:
  1. 访问 https://open.tianyancha.com 注册
  2. 创建应用 → 获取 AppKey / AppSecret
  3. 充值后才能调用
  4. 将 AppSecret 设为环境变量 TIANYANCHA_TOKEN

免费替代: 国家企业信用信息公示系统 (gsxt.gov.cn, 完全免费但需申请白名单)
"""

import os
import httpx
from typing import Any
from src.agents.tools.base import ToolBase


class TianyanchaTool(ToolBase):
    name = "tianyancha"
    description = (
        "查询中国公司工商信息: 企业基本信息、股东、法人、注册资本、经营状态等。"
        "PAID SERVICE — 企业基本信息 ¥0.15/次, 司法风险 ¥1.50/次。"
        "需在天眼查开放平台注册并充值。设置 TIANYANCHA_TOKEN 后可用。"
        "如需免费方案, 可用 web_scrape 访问 gsxt.gov.cn 国家企业信用信息公示系统。"
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "search (搜索公司), baseinfo (公司基本信息), "
                           "shareholders (股东信息), legal_risk (司法风险简版)",
        },
        "keyword": {"type": "string", "description": "公司名关键词 (action=search)"},
        "company_name": {"type": "string", "description": "公司全称 (action=baseinfo/shareholders/legal_risk)"},
        "page_size": {"type": "integer", "description": "搜索结果数 (default 10, max 20)"},
    }

    BASE = "https://api.tianyancha.com"

    def _token(self) -> str | None:
        return os.environ.get("TIANYANCHA_TOKEN")

    def _headers(self) -> dict:
        token = self._token()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    async def execute(self, **kwargs) -> dict[str, Any]:
        token = self._token()
        if not token:
            return {
                "error": (
                    "天眼查 API key 未设置。"
                    "天眼查是付费服务 (企业基本信息 ¥0.15/次)。"
                    "如需使用: 访问 open.tianyancha.com 注册 → 创建应用获取 AppSecret → 充值 → 设置环境变量 TIANYANCHA_TOKEN。"
                    "免费替代方案: 用 web_scrape 工具访问 gsxt.gov.cn 查询企业工商信息。"
                ),
            }

        action = kwargs.get("action", "search")

        try:
            if action == "search":
                return await self._search(kwargs)
            elif action == "baseinfo":
                return await self._baseinfo(kwargs)
            elif action == "shareholders":
                return await self._shareholders(kwargs)
            elif action == "legal_risk":
                return await self._legal_risk(kwargs)
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": f"天眼查查询失败: {e}"}

    async def _search(self, kwargs: dict) -> dict[str, Any]:
        keyword = kwargs.get("keyword", "")
        if not keyword:
            return {"error": "keyword is required"}

        page_size = min(int(kwargs.get("page_size", 10)), 20)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/search/v2/company",
                params={"keyword": keyword, "pageSize": page_size},
                headers=self._headers(),
            )
            if resp.status_code == 401:
                return {"error": "天眼查 token 无效或已过期"}
            if resp.status_code == 429:
                return {"error": "配额已用完或账户余额不足"}
            resp.raise_for_status()
            data = resp.json()

        items = []
        raw_items = data.get("result", {}).get("items", [])
        for item in raw_items:
            items.append({
                "name": item.get("name", ""),
                "legal_person": item.get("legalPersonName", ""),
                "reg_capital": item.get("regCapital", ""),
                "status": item.get("regStatus", ""),
                "established": item.get("estiblishTime", ""),
                "credit_code": item.get("creditCode", ""),
                "category": item.get("companyOrgType", ""),
            })

        return {"keyword": keyword, "total": data.get("result", {}).get("total", 0), "items": items}

    async def _baseinfo(self, kwargs: dict) -> dict[str, Any]:
        company_name = kwargs.get("company_name", "")
        if not company_name:
            return {"error": "company_name is required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/open/baseinfo/normal",
                params={"keyword": company_name},
                headers=self._headers(),
            )
            if resp.status_code == 401:
                return {"error": "天眼查 token 无效或已过期"}
            if resp.status_code == 429:
                return {"error": "配额已用完或账户余额不足"}
            resp.raise_for_status()
            data = resp.json()

        result = data.get("result", {})
        return {
            "company_name": result.get("name", ""),
            "alias": result.get("alias", ""),
            "legal_person": result.get("legalPersonName", ""),
            "reg_capital": result.get("regCapital", ""),
            "reg_status": result.get("regStatus", ""),
            "established_date": result.get("estiblishTime", ""),
            "credit_code": result.get("creditCode", ""),
            "business_scope": result.get("businessScope", ""),
            "address": result.get("regLocation", ""),
            "industry": result.get("industry", ""),
        }

    async def _shareholders(self, kwargs: dict) -> dict[str, Any]:
        company_name = kwargs.get("company_name", "")
        if not company_name:
            return {"error": "company_name is required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/open/holder/normal",
                params={"keyword": company_name},
                headers=self._headers(),
            )
            if resp.status_code == 401:
                return {"error": "天眼查 token 无效或已过期"}
            if resp.status_code == 429:
                return {"error": "配额已用完或账户余额不足"}
            resp.raise_for_status()
            data = resp.json()

        holders = []
        for h in data.get("result", {}).get("items", []):
            holders.append({
                "name": h.get("name", ""),
                "ratio": h.get("capital", ""),
                "type": h.get("holderType", ""),
            })

        return {"company_name": company_name, "shareholders": holders}

    async def _legal_risk(self, kwargs: dict) -> dict[str, Any]:
        company_name = kwargs.get("company_name", "")
        if not company_name:
            return {"error": "company_name is required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/open/legal-risk/simple",
                params={"keyword": company_name},
                headers=self._headers(),
            )
            if resp.status_code == 401:
                return {"error": "天眼查 token 无效或已过期"}
            if resp.status_code == 429:
                return {"error": "配额已用完或账户余额不足"}
            resp.raise_for_status()
            data = resp.json()

        result = data.get("result", {})
        return {
            "company_name": company_name,
            "lawsuit_count": result.get("lawsuitCount", 0),
            "dishonest_count": result.get("dishonestCount", 0),
            "enforcement_count": result.get("enforcementCount", 0),
            "abnormal_count": result.get("abnormalCount", 0),
            "punishment_count": result.get("punishmentCount", 0),
        }
