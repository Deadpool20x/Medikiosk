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
from backend.models.schema import HealthResponse, ErrorResponse
from backend.db import init_db
from backend.routers import session, doctor

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite tables on startup idempotently
    init_db()
    yield

app = FastAPI(
    title="MediKiosk API",
    version="0.1.0",
    description="AI-assisted pre-consultation clinical case-taking backend",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers to prevent raw stack trace leakage to client
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
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
    return HealthResponse(status="ok")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("BACKEND_PORT", "8000")),
        reload=True,
    )
