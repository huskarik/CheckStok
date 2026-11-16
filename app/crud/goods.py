from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Good
from app.schemas.good import GoodCreate, GoodUpdate


class DuplicateSkuError(Exception):
    """Артикул уже принадлежит другому товару."""


def list_goods(db: Session) -> list[Good]:
    statement = select(Good).order_by(Good.id)
    return list(db.scalars(statement))


def get_good(db: Session, good_id: int) -> Good | None:
    return db.get(Good, good_id)


def _save(db: Session, good: Good) -> Good:
    db.add(good)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Проверяем именно ограничение артикула, остальные ошибки не маскируем.
        diagnostic = getattr(exc.orig, "diag", None)
        if getattr(diagnostic, "constraint_name", None) == "uq_goods_sku":
            raise DuplicateSkuError from exc
        raise
    db.refresh(good)
    return good


def create_good(db: Session, data: GoodCreate) -> Good:
    return _save(db, Good(**data.model_dump()))


def update_good(db: Session, good: Good, data: GoodUpdate) -> Good:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(good, field, value)
    return _save(db, good)


def delete_good(db: Session, good: Good) -> None:
    db.delete(good)
    db.commit()
