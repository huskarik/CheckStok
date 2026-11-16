from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import Database, RecordId
from app.crud import goods as crud
from app.models import Good
from app.schemas.good import GoodCreate, GoodRead, GoodUpdate

router = APIRouter(prefix="/goods", tags=["Товары"])


def _get_or_404(db: Database, good_id: int) -> Good:
    good = crud.get_good(db, good_id)
    if good is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return good


@router.get("", response_model=list[GoodRead], summary="Список товаров")
def list_goods(db: Database):
    return crud.list_goods(db)


@router.post(
    "",
    response_model=GoodRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить товар",
    responses={409: {"description": "Артикул уже существует"}},
)
def create_good(data: GoodCreate, db: Database):
    return crud.create_good(db, data)


@router.get(
    "/{good_id}",
    response_model=GoodRead,
    summary="Получить товар",
    responses={404: {"description": "Товар не найден"}},
)
def get_good(good_id: RecordId, db: Database):
    return _get_or_404(db, good_id)


@router.patch(
    "/{good_id}",
    response_model=GoodRead,
    summary="Изменить товар",
    responses={
        404: {"description": "Товар не найден"},
        409: {"description": "Артикул уже существует"},
    },
)
def update_good(good_id: RecordId, data: GoodUpdate, db: Database):
    return crud.update_good(db, _get_or_404(db, good_id), data)


@router.delete(
    "/{good_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить товар",
    responses={404: {"description": "Товар не найден"}},
)
def delete_good(good_id: RecordId, db: Database) -> Response:
    crud.delete_good(db, _get_or_404(db, good_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
