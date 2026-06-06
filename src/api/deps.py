import logging
import os
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway
from src.dag.scheduler import DAGScheduler

logger = logging.getLogger(__name__)

_store: GraphStore | None = None
_scheduler: DAGScheduler | None = None
_gateway: LLMGateway | None = None
_audit_logger = None


def _ensure_data_dir():
    os.makedirs("data", exist_ok=True)


def get_store() -> GraphStore:
    global _store
    if _store is None:
        _ensure_data_dir()
        _store = GraphStore(db_path="data/knowledge_graph.db")
    return _store


def get_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        # Configure an OpenAI-compatible provider from .env as the default LLM.
        # Falls back to Anthropic if ANTHROPIC_API_KEY is set instead.
        has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
        if not has_anthropic:
            model = os.getenv("LLM_DEFAULT_MODEL", "deepseek-chat")
            _gateway = LLMGateway(
                default_model=model,
                model_map={
                    "reasoning": model,
                    "analysis": model,
                    "batch": model,
                },
                provider_map={
                    model: "openai_compatible",
                },
            )
        else:
            _gateway = LLMGateway()
    return _gateway


def get_scheduler() -> DAGScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = DAGScheduler()
    return _scheduler


def get_audit_logger():
    global _audit_logger
    if _audit_logger is None:
        try:
            from src.infrastructure.audit import AuditLogger
            _ensure_data_dir()
            _audit_logger = AuditLogger(db_path="data/audit.db")
        except ImportError:
            logger.warning("audit module not available — step traces disabled")
            _audit_logger = None
    return _audit_logger
