from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate


def list_warehouses(db: Session) -> list[Warehouse]:
    statement = select(Warehouse).order_by(Warehouse.id)
    return list(db.scalars(statement))


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse | None:
    return db.get(Warehouse, warehouse_id)


def create_warehouse(db: Session, data: WarehouseCreate) -> Warehouse:
    warehouse = Warehouse(**data.model_dump())
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def update_warehouse(
    db: Session, warehouse: Warehouse, data: WarehouseUpdate
) -> Warehouse:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(warehouse, field, value)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def delete_warehouse(db: Session, warehouse: Warehouse) -> None:
    db.delete(warehouse)
    db.commit()
