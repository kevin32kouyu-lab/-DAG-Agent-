from dataclasses import dataclass, field
from src.infrastructure.config import Config
from src.infrastructure.audit import AuditLogger


@dataclass
class SourceFetchResult:
    source: str
    url: str
    tier: int  # 0=primary, 1=tier1, 2=tier2, -1=unavailable
    tier_label: str
    data: dict | None = None
    error: str | None = None


@dataclass
class DegradationHandler:
    config: Config
    audit: AuditLogger = field(default_factory=AuditLogger)

    TIER_KEYS = ["primary", "tier1", "tier2", "unavailable"]

    def get_tiers(self, source: str) -> dict:
        tiers = {}
        for key in ("saas", "degradation"):
            src_tiers = self.config.get(f"{key}.degradation_tiers.{source}")
            if src_tiers:
                tiers = src_tiers
                break
        return tiers

    def get_tier_strategy(self, source: str, tier: int) -> str:
        tiers = self.get_tiers(source)
        key = self.TIER_KEYS[min(tier, 3)] if tier >= 0 else "unavailable"
        return tiers.get(key, f"降级策略 tier={tier}")

    def is_exhausted(self, source: str, tier: int) -> bool:
        tiers = self.get_tiers(source)
        if not tiers:
            return True
        max_tier = sum(1 for k in tiers if k.startswith("tier"))
        return tier > max_tier

    def log_degradation(self, task_id: str, node_id: str, source: str,
                        tier: int, reason: str, url: str = "") -> None:
        tier_label = "primary" if tier == 0 else f"tier{tier}" if tier > 0 else "unavailable"
        fallback = self.get_tier_strategy(source, tier)
        if self.audit is not None:
            self.audit.log_event(task_id, node_id, "Collector", "source_degraded", {
                "source": source,
                "url": url,
                "tier": tier,
                "tier_label": tier_label,
                "reason": reason,
                "fallback_used": fallback,
            })

    def next_tier(self, source: str, current_tier: int) -> int:
        if self.is_exhausted(source, current_tier + 1):
            return -1
        return current_tier + 1
