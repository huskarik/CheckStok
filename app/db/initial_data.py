from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert

from app.core.document_types import DOCUMENT_TYPE_NAMES
from app.models import DocumentType


def initialize_document_types(engine: Engine) -> None:
    """Добавляет отсутствующие типы документов при запуске приложения."""
    with engine.begin() as connection:
        connection.execute(
            insert(DocumentType)
            .values(
                [
                    {"type": kind.value, "name": name}
                    for kind, name in DOCUMENT_TYPE_NAMES.items()
                ]
            )
            .on_conflict_do_nothing(index_elements=[DocumentType.type])
        )
