import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import analyse, compare, ocr, receipts
from app.config import settings
from app.limiter import limiter

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Receipt Tracker API",
    description="Price comparison backend for Canadian grocery and dollar store receipts",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(ocr.router)
app.include_router(receipts.router)
app.include_router(compare.router)
app.include_router(analyse.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred"})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
