from pydantic import BaseModel, ConfigDict

from app.schemas.common import InputSchema, Name, UpdateSchema


class WarehouseCreate(InputSchema):
    name: Name


class WarehouseUpdate(UpdateSchema):
    name: Name | None = None


class WarehouseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
