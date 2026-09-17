import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionLocal
from app.routers import auth, products, reports, users

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("almoxarifado")

DESCRIPTION = """
API de controle de estoque para almoxarifado de pequena empresa.

**Como testar:** clique em *Authorize* e entre com uma das contas de demonstração
(os dados voltam ao original todo dia):

| Perfil | Email | Senha | Pode |
|---|---|---|---|
| operator | operador@demo.dev | demo-operador-2026 | consultar e registrar entradas e saídas |
| viewer | leitura@demo.dev | demo-leitura-2026 | só consultar |

A conta **admin** não é pública: cadastro de produtos, usuários e auditoria ficam restritos.
"""

app = FastAPI(
    title="API de Almoxarifado",
    version="1.0.0",
    description=DESCRIPTION,
    redoc_url=None,
)

MAX_BODY = 32 * 1024
DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > MAX_BODY):
        return JSONResponse({"detail": "Request body too large"}, status_code=413)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    # a pagina /docs usa o Swagger UI do CDN; o resto da API nao serve HTML
    response.headers["Content-Security-Policy"] = (
        DOCS_CSP if request.url.path in ("/docs", "/docs/oauth2-redirect") else "default-src 'none'; frame-ancestors 'none'"
    )
    if request.url.path.startswith(("/auth", "/users", "/products", "/reports", "/audit-logs")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # devolve onde esta o erro sem ecoar o valor enviado (pode ser senha)
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]) or e["loc"][0], "message": e["msg"]} for e in exc.errors()]
    return JSONResponse({"detail": "Invalid request", "errors": errors}, status_code=422)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    log.error("database error on %s %s: %s", request.method, request.url.path, type(exc).__name__)
    return JSONResponse({"detail": "Database unavailable, try again"}, status_code=503)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", tags=["health"], summary="Health check")
def health():
    with SessionLocal() as db:
        db.execute(text("select 1"))
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(products.router)
app.include_router(reports.router)
app.include_router(users.router)
