from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.api.router import router
from app.core.config import get_settings
from app.core.exceptions import BusinessError
from app.crud.goods import DuplicateSkuError
from app.db.initial_data import initialize_document_types
from app.db.session import get_engine

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    engine = get_engine()
    try:
        initialize_document_types(engine)
        yield
    finally:
        engine.dispose()


app = FastAPI(
    title=get_settings().app_name,
    description="Справочники, документы движения и текущие остатки CheckStock",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError) -> JSONResponse:
    content = {"detail": exc.detail, "code": exc.code}
    if exc.context is not None:
        content["context"] = exc.context
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    if getattr(exc.orig, "sqlstate", None) == "23503":
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Запись связана с другими данными. Удаление или изменение запрещено",
                "code": "reference_conflict",
            },
        )
    raise exc


@app.exception_handler(DuplicateSkuError)
async def duplicate_sku_handler(
    request: Request, exc: DuplicateSkuError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "Товар с таким артикулом уже существует"},
    )


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
