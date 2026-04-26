"""
QSignHub API — Qualified Electronic Signatures as a Service
eIDAS-compliant REST API (QES / AES / SES)
"""
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text

from app.config import get_settings
from app.database import engine, Base
from app.routers import (
    auth,
    api_keys,
    documents,
    signature_requests,
    signatories,
    signing_sessions,
    webhooks,
    certificates,
    validation,
    audit_logs,
    organizations,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## QSignHub API

Kwalifikowane podpisy elektroniczne jako usługa — REST API zgodne z eIDAS.

### Poziomy podpisów (eIDAS)
| Poziom | Skrót | Opis |
|--------|-------|------|
| Kwalifikowany Podpis Elektroniczny | **QES** | Najwyższy poziom prawny, równoważny podpisowi odręcznemu |
| Zaawansowany Podpis Elektroniczny | **AES** | Powiązany jednoznacznie z podpisującym |
| Zwykły Podpis Elektroniczny | **SES** | Podstawowy poziom, zgoda kliknięciem |

### Formaty podpisów
- **PAdES** — PDF Advanced Electronic Signatures
- **XAdES** — XML Advanced Electronic Signatures
- **CAdES** — CMS Advanced Electronic Signatures

### Przepływ integracji
1. Prześlij dokument → `POST /documents`
2. Utwórz żądanie podpisu → `POST /signature-requests`
3. Wyślij zaproszenia → `POST /signature-requests/{id}/send`
4. Odbierz zdarzenia przez webhook
5. Pobierz podpisany dokument → `GET /documents/{id}/download`

### Uwierzytelnianie
- **Klucze API** (`X-API-Key`) — do integracji serwer-serwer
- **JWT Bearer** (`Authorization: Bearer ...`) — do panelu użytkownika
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{elapsed}ms"
    return response


# ── Exception handlers ─────────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "details": [
                {
                    "field": ".".join(str(loc) for loc in err["loc"][1:]),
                    "message": err["msg"],
                    "code": err["type"],
                }
                for err in exc.errors()
            ],
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    if settings.DEBUG:
        raise exc
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_error", "message": "An unexpected error occurred"},
    )


# ── Routers ────────────────────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(organizations.router, prefix=API_PREFIX)
app.include_router(api_keys.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)
app.include_router(signature_requests.router, prefix=API_PREFIX)
app.include_router(signatories.router, prefix=API_PREFIX)
app.include_router(signing_sessions.router, prefix=API_PREFIX)
app.include_router(webhooks.router, prefix=API_PREFIX)
app.include_router(certificates.router, prefix=API_PREFIX)
app.include_router(validation.router, prefix=API_PREFIX)
app.include_router(audit_logs.router, prefix=API_PREFIX)


# ── Health & meta ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health check")
async def health_check():
    """Liveness probe — returns 200 when the service is up."""
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/health/ready", tags=["System"], summary="Readiness check")
async def readiness_check():
    """Readiness probe — checks DB connectivity."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    ready = db_status == "ok"
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ready" if ready else "not_ready", "database": db_status},
    )


@app.get("/", tags=["System"], include_in_schema=False)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
    }
