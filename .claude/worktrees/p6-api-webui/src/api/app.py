from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import task, report, trace, agent
from src.api.websocket import router as ws_router

app = FastAPI(title="Competitive Analysis Agent System", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(task.router, prefix="/api", tags=["task"])
app.include_router(report.router, prefix="/api", tags=["report"])
app.include_router(trace.router, prefix="/api", tags=["trace"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(ws_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
