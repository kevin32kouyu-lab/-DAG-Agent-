from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import task, report, trace, agent
from src.api.websocket import router as ws_router
from src.infrastructure.health import HealthCheck

app = FastAPI(title="Competitive Analysis Agent System", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(task.router, prefix="/api", tags=["task"])
app.include_router(report.router, prefix="/api", tags=["report"])
app.include_router(trace.router, prefix="/api", tags=["trace"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(ws_router)

health_check = HealthCheck()


@app.get("/api/health")
async def health():
    unhealthy = health_check.get_unhealthy_agents()
    timed_out = health_check.get_timed_out_tasks()
    return {
        "status": "degraded" if (unhealthy or timed_out) else "ok",
        "unhealthy_agents": unhealthy,
        "timed_out_tasks": timed_out,
        "agent_count": len(health_check.agent_heartbeats),
        "running_tasks": len(health_check.task_timeouts),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
