from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Good(Base):
    __tablename__ = "goods"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class DocumentType(Base):
    __tablename__ = "documents_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    document_moves: Mapped[list[DocumentMove]] = relationship(
        back_populates="document_type_ref"
    )


class DocumentMove(Base):
    __tablename__ = "documents_moves"
    __table_args__ = (
        # Ограничение на указание одинаковых складов для перемещения
        CheckConstraint(
            "source_warehouse IS NULL OR target_warehouse IS NULL OR "
            "source_warehouse <> target_warehouse",
            name="different_warehouses",
        ),
        # Ограничение на отмену только одного документа. 
        # У настоящего is_deleted=False и нет reversal_of_id
        # У ОТМЕНЯЮЩЕГО is_deleted-True и указан reversal_of_id (айди связанного документа, который он отменяет)
        CheckConstraint(
            "(is_deleted AND reversal_of_id IS NOT NULL) OR "
            "(NOT is_deleted AND reversal_of_id IS NULL)",
            name="deletion_requires_original",
        ),
        # Ограничение на связь 
        CheckConstraint("reversal_of_id != id", name="not_own_reversal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    document_type: Mapped[str] = mapped_column(
        String(64), ForeignKey("documents_types.type"), nullable=False
    )
    source_warehouse: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id"), nullable=True
    )
    target_warehouse: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id"), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    is_delivered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    reversal_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents_moves.id", ondelete="RESTRICT"),
        unique=True,
        nullable=True,
    )

    document_type_ref: Mapped[DocumentType] = relationship(
        back_populates="document_moves"
    )
    source: Mapped[Warehouse | None] = relationship(foreign_keys=[source_warehouse])
    target: Mapped[Warehouse | None] = relationship(foreign_keys=[target_warehouse])
    stock_moves: Mapped[list[StockMove]] = relationship(
        back_populates="document_move",
        order_by="StockMove.id",
        passive_deletes="all",
    )
    original: Mapped[DocumentMove | None] = relationship(
        remote_side=[id],
        foreign_keys=[reversal_of_id],
        back_populates="reversal",
    )
    reversal: Mapped[DocumentMove | None] = relationship(
        foreign_keys=[reversal_of_id],
        back_populates="original",
        uselist=False,
        passive_deletes="all",
    )


class StockMove(Base):
    __tablename__ = "stock_moves"
    __table_args__ = (
        UniqueConstraint("document_move_id", "good_id"),
        CheckConstraint("quantity != 0", name="quantity_not_zero"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_move_id: Mapped[int] = mapped_column(
        ForeignKey("documents_moves.id"), nullable=False
    )
    good_id: Mapped[int] = mapped_column(ForeignKey("goods.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    document_move: Mapped[DocumentMove] = relationship(back_populates="stock_moves")
    good: Mapped[Good] = relationship()


class StockBalance(Base):
    __tablename__ = "stock_balances"
    __table_args__ = (
        # Дополнительная проверка что available у нас передаётся правильно
        CheckConstraint("available = stock - reserve", name="available_matches_stock"),
    )

    good_id: Mapped[int] = mapped_column(ForeignKey("goods.id"), primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id"), primary_key=True
    )
    stock: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    reserve: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    available: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    good: Mapped[Good] = relationship()
    warehouse: Mapped[Warehouse] = relationship()
