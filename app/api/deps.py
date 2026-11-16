from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.inventory import InventoryService

Database = Annotated[Session, Depends(get_db)]
RecordId = Annotated[int, Path(gt=0)]


def get_inventory_service(db: Database) -> InventoryService:
    return InventoryService(db)


Inventory = Annotated[InventoryService, Depends(get_inventory_service)]
