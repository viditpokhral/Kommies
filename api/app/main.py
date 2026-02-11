from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from app.core.config import settings
from app.api.v1.router import router as v1_router
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting Comment Platform API...")
    yield
    # Shutdown
    await engine.dispose()
    print("Shutdown complete.")


app = FastAPI(
    title="Comment Platform API",
    description="Embeddable comment system API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REQUEST TIMING MIDDLEWARE ─────────────────────────────────────────────────
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(round((time.time() - start) * 1000, 2))
    return response


# ── GLOBAL EXCEPTION HANDLER ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── ROUTES ────────────────────────────────────────────────────────────────────
app.include_router(v1_router, prefix="/api")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": "1.0.0"}