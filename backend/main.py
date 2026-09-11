import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load .env from project root so os.environ picks up API keys before any
# provider module reads them.  Must happen before backend imports.
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
from backend.models.schema import HealthResponse, ErrorResponse
from backend.db import init_db, get_db_connection
from backend.routers import session, doctor

logger = logging.getLogger("medikiosk")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite tables and performance indexes on startup idempotently
    init_db()
    yield

app = FastAPI(
    title="MediKiosk API",
    version="0.1.0",
    description="AI-assisted pre-consultation clinical case-taking backend",
    lifespan=lifespan
)

# Configure CORS with environment variable override and local fallback
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
if allowed_origins_env:
    origins = [orig.strip() for orig in allowed_origins_env.split(",") if orig.strip()]
else:
    origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers to prevent raw stack trace leakage to client while logging for observability
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="An internal server error occurred. Progress is safely saved.",
            retryable=True
        ).model_dump()
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=ErrorResponse(
            error="Invalid input provided. Please verify the submitted data.",
            retryable=False
        ).model_dump()
    )

# Include Routers
app.include_router(session.router)
app.include_router(doctor.router)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    # Verify active database connectivity
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1;").fetchone()
        conn.close()
    except Exception as e:
        logger.error("Database health check probe failed: %s", e)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "error": "Database connectivity failure"}
        )
    return HealthResponse(status="ok")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("BACKEND_PORT", "8000")),
        reload=True,
    )
