from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

PositiveInteger = Annotated[int, Field(strict=True, gt=0)]

Sku = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class InputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UpdateSchema(InputSchema):
    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Укажите хотя бы одно поле для изменения")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"Поле {field} не может быть null")
        return self
