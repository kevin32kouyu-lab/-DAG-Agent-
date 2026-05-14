import pytest
import tempfile
from pathlib import Path
from src.infrastructure.config import Config
from src.infrastructure.degradation import DegradationHandler


@pytest.fixture
def handler():
    with tempfile.TemporaryDirectory() as tmp:
        yaml_path = Path(tmp) / "saas.yaml"
        yaml_path.write_text("""\
degradation_tiers:
  G2:
    primary: "网页采集（评分+评论摘要）"
    tier1: "仅提取公开评分（首页星级）"
    tier2: "搜索引擎缓存摘要"
    unavailable: "标记 G2 数据缺失"
  ProductHunt:
    primary: "网页采集公开页面"
    tier1: "ProductHunt RSS"
    tier2: "跳过"
""", encoding="utf-8")
        cfg = Config(config_dir=tmp)
        yield DegradationHandler(config=cfg, audit=None)


def test_get_tiers_g2(handler):
    tiers = handler.get_tiers("G2")
    assert "primary" in tiers
    assert "tier1" in tiers
    assert "tier2" in tiers
    assert tiers["primary"] == "网页采集（评分+评论摘要）"


def test_get_tiers_producthunt(handler):
    tiers = handler.get_tiers("ProductHunt")
    assert tiers["primary"] == "网页采集公开页面"
    assert tiers["tier1"] == "ProductHunt RSS"
    assert tiers["tier2"] == "跳过"


def test_get_tiers_unknown_source(handler):
    tiers = handler.get_tiers("UnknownSource")
    assert tiers == {}


def test_is_not_exhausted_primary(handler):
    assert not handler.is_exhausted("G2", 0)


def test_is_not_exhausted_tier1(handler):
    assert not handler.is_exhausted("G2", 1)


def test_is_exhausted_after_tier2(handler):
    assert handler.is_exhausted("G2", 3)


def test_is_exhausted_unknown_source(handler):
    assert handler.is_exhausted("UnknownSource", 0)


def test_next_tier_from_primary(handler):
    assert handler.next_tier("G2", 0) == 1


def test_next_tier_from_tier1(handler):
    assert handler.next_tier("G2", 1) == 2


def test_next_tier_to_exhausted(handler):
    assert handler.next_tier("G2", 2) == -1


def test_get_tier_strategy(handler):
    assert "网页采集" in handler.get_tier_strategy("G2", 0)
    assert "公开评分" in handler.get_tier_strategy("G2", 1)
    assert "搜索引擎" in handler.get_tier_strategy("G2", 2)
    assert "数据缺失" in handler.get_tier_strategy("G2", -1)


def test_log_degradation_without_audit(handler):
    # Should not raise when audit is None
    handler.log_degradation("task1", "node1", "G2", 1, "HTTP 403", "https://g2.com/product")


def test_log_degradation_with_audit(handler):
    from src.infrastructure.audit import AuditLogger
    handler.audit = AuditLogger(":memory:")
    handler.log_degradation("task1", "node1", "G2", 1, "HTTP 403", "https://g2.com/product")
    logs = handler.audit.get_task_log("task1")
    assert len(logs) == 1
    assert logs[0]["event"] == "source_degraded"
    assert "HTTP 403" in logs[0]["data"]


def test_source_fetch_result_defaults():
    from src.infrastructure.degradation import SourceFetchResult
    r = SourceFetchResult(source="G2", url="https://example.com", tier=0, tier_label="primary")
    assert r.data is None
    assert r.error is None
    assert r.tier == 0


def test_source_fetch_result_with_error():
    from src.infrastructure.degradation import SourceFetchResult
    r = SourceFetchResult(source="G2", url="https://example.com", tier=1, tier_label="tier1",
                          error="Timeout")
    assert r.error == "Timeout"
    assert r.data is None
