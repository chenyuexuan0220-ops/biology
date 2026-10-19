import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from app.api.routes import router
from app.api.lessons import router as lessons_router
from app.api.source_drafts import router as source_drafts_router
from app.config import settings

app = FastAPI(title="生物竞赛 AI 学习系统", version="1.2.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)
app.include_router(lessons_router)
app.include_router(source_drafts_router)
logger = logging.getLogger("biology.api")


@app.exception_handler(IntegrityError)
async def conflict_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": "数据已存在或关联约束冲突，请刷新后重试"})


@app.middleware("http")
async def timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.perf_counter() - start:.4f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    logger.info("%s %s %s %.3fs", request.method, request.url.path, response.status_code, time.perf_counter() - start)
    return response


@app.get("/health")
def health() -> dict:
    from sqlalchemy import text
    from app.db import engine

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "version": "1.2.1"}
