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
        # Priority: 1) DeepSeek (fastest), 2) Anthropic proxy, 3) Default Anthropic
        has_deepseek = bool(os.getenv("DEEPSEEK_API_KEY"))
        has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))

        if has_deepseek:
            # Use DeepSeek as default (fastest response)
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
        elif has_anthropic:
            # Use Anthropic proxy
            model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
            _gateway = LLMGateway(
                default_model=model,
                model_map={
                    "reasoning": model,
                    "analysis": model,
                    "batch": model,
                },
            )
        else:
            # Fallback to default Anthropic
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
