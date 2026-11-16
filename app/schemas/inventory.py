from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StrictBool

from app.core.document_types import DocumentKind
from app.schemas.common import InputSchema, PositiveInteger


class DocumentItemCreate(InputSchema):
    good_id: PositiveInteger
    quantity: PositiveInteger


class DocumentCreate(InputSchema):
    document_type: DocumentKind
    source_warehouse: PositiveInteger | None = None
    target_warehouse: PositiveInteger | None = None
    fbo: StrictBool = False
    items: Annotated[list[DocumentItemCreate], Field(min_length=1)]


class DocumentTypeRead(BaseModel):
    type: DocumentKind
    name: str


class DocumentDeliveryUpdate(InputSchema):
    is_delivered: StrictBool = True


class DocumentItemRead(BaseModel):
    id: int
    good_id: int
    sku: str
    name: str
    quantity: int
    in_transit: int


class DocumentRead(BaseModel):
    id: int
    created_at: datetime
    document_type: DocumentKind
    document_type_name: str
    source_warehouse: int | None
    target_warehouse: int | None
    is_deleted: bool
    is_delivered: bool
    total_in_transit: int
    reversal_of_id: int | None
    is_cancelled: bool
    reversal_id: int | None
    items: list[DocumentItemRead]


class WarehouseAvailability(BaseModel):
    warehouse_id: int
    name: str
    available: int
    reserve: int


class StockBalanceRead(BaseModel):
    good_id: int
    sku: str
    name: str
    total_available: int
    total_reserve: int
    total_in_transit: int
    in_transit_fbo: int
    in_transit_fbs: int
    in_transit_transfer: int
    warehouses: list[WarehouseAvailability]


class ReserveChange(InputSchema):
    good_id: PositiveInteger
    warehouse_id: PositiveInteger
    quantity: PositiveInteger


class ReserveRead(BaseModel):
    good_id: int
    warehouse_id: int
    stock: int
    reserve: int
    available: int
