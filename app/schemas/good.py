from pydantic import BaseModel, ConfigDict

from app.schemas.common import InputSchema, Name, Sku, UpdateSchema


class GoodCreate(InputSchema):
    sku: Sku
    name: Name


class GoodUpdate(UpdateSchema):
    sku: Sku | None = None
    name: Name | None = None


class GoodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
