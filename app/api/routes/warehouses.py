from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import Database, RecordId
from app.crud import warehouses as crud
from app.models import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseRead, WarehouseUpdate

router = APIRouter(prefix="/warehouses", tags=["Склады"])


def _get_or_404(db: Database, warehouse_id: int) -> Warehouse:
    warehouse = crud.get_warehouse(db, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Склад не найден")
    return warehouse


@router.get("", response_model=list[WarehouseRead], summary="Список складов")
def list_warehouses(db: Database):
    return crud.list_warehouses(db)


@router.post(
    "",
    response_model=WarehouseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить склад",
)
def create_warehouse(data: WarehouseCreate, db: Database):
    return crud.create_warehouse(db, data)


@router.get(
    "/{warehouse_id}",
    response_model=WarehouseRead,
    summary="Получить склад",
    responses={404: {"description": "Склад не найден"}},
)
def get_warehouse(warehouse_id: RecordId, db: Database):
    return _get_or_404(db, warehouse_id)


@router.patch(
    "/{warehouse_id}",
    response_model=WarehouseRead,
    summary="Изменить склад",
    responses={404: {"description": "Склад не найден"}},
)
def update_warehouse(warehouse_id: RecordId, data: WarehouseUpdate, db: Database):
    return crud.update_warehouse(db, _get_or_404(db, warehouse_id), data)


@router.delete(
    "/{warehouse_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить склад",
    responses={404: {"description": "Склад не найден"}},
)
def delete_warehouse(warehouse_id: RecordId, db: Database) -> Response:
    crud.delete_warehouse(db, _get_or_404(db, warehouse_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
