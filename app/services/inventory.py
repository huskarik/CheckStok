from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import and_, func, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.document_types import (
    DOCUMENT_TYPE_NAMES, SHIPMENT_TYPES, TRANSIT_TYPES, DocumentKind,
)
from app.core.exceptions import ConflictError, InvalidOperationError, NotFoundError
from app.models import DocumentMove, Good, StockBalance, StockMove, Warehouse
from app.schemas.inventory import (
    DocumentCreate, DocumentItemRead, DocumentRead, DocumentTypeRead,
    ReserveChange, ReserveRead, StockBalanceRead, WarehouseAvailability,
)

BalanceKey = tuple[int, int]  # (good_id, warehouse_id)


class InventoryService:
    """Проведение документов, доставка, резервы и чтение остатков.

    Команды владеют транзакцией переданной сессии.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    @contextmanager
    def _transaction(self) -> Generator[None]:
        try:
            with self.db.begin():
                yield
        except IntegrityError as exc:
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if constraint == "uq_documents_moves_reversal_of_id":
                raise ConflictError(
                    "Документ уже отменён", code="document_already_cancelled"
                ) from exc
            if getattr(exc.orig, "sqlstate", None) == "23503":
                raise ConflictError(
                    "Товар, склад или связанный документ отсутствует в БД",
                    code="reference_conflict",
                ) from exc
            raise
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) == "22003":
                raise InvalidOperationError(
                    "Числовое значение выходит за допустимый диапазон БД",
                    code="numeric_value_out_of_range",
                ) from exc
            if getattr(exc.orig, "sqlstate", None) in {"40001", "40P01"}:
                raise ConflictError(
                    "Данные одновременно изменяются другим запросом. Повторите операцию",
                    code="concurrent_operation",
                ) from exc
            raise

    @staticmethod
    def get_document_types() -> list[DocumentTypeRead]:
        return [
            DocumentTypeRead(type=kind, name=name)
            for kind, name in DOCUMENT_TYPE_NAMES.items()
        ]

    def create_document(self, data: DocumentCreate) -> DocumentRead:
        with self._transaction():
            kind = data.document_type
            if data.fbo:
                if kind not in SHIPMENT_TYPES:
                    raise InvalidOperationError(
                        "Флаг FBO допустим только для отправки", code="invalid_fbo_flag"
                    )
                kind = DocumentKind.SHIPMENT_FBO
            self._validate_warehouses(kind, data.source_warehouse, data.target_warehouse)
            quantities: dict[int, int] = defaultdict(int)
            for item in data.items:
                quantities[item.good_id] += item.quantity
            document = self._record_document(
                kind=kind,
                source_warehouse=data.source_warehouse,
                target_warehouse=data.target_warehouse,
                quantities=quantities,
            )
            return self.get_document(document.id)

    def create_reserve(self, data: ReserveChange) -> ReserveRead:
        return self._change_reserve(data, release=False)

    def release_reserve(self, data: ReserveChange) -> ReserveRead:
        return self._change_reserve(data, release=True)

    def _change_reserve(self, data: ReserveChange, *, release: bool) -> ReserveRead:
        with self._transaction():
            key = (data.good_id, data.warehouse_id)
            balance = self._lock_balances([key])[key]
            if release and data.quantity > balance.reserve:
                raise ConflictError(
                    "Нельзя снять больше зарезервированного количества",
                    code="insufficient_reserve",
                    context={
                        "good_id": data.good_id, "warehouse_id": data.warehouse_id,
                        "requested": data.quantity,
                        "reserve": balance.reserve, "available": balance.available,
                    },
                )
            if not release and data.quantity > balance.available:
                raise ConflictError(
                    "Недостаточно доступного товара для резерва",
                    code="insufficient_stock",
                    context={"shortages": [{
                        "good_id": data.good_id, "warehouse_id": data.warehouse_id,
                        "requested": data.quantity, "available": balance.available,
                    }]},
                )
            balance.reserve += -data.quantity if release else data.quantity
            balance.available = balance.stock - balance.reserve
            self.db.flush()
            return ReserveRead(
                good_id=balance.good_id, warehouse_id=balance.warehouse_id,
                stock=balance.stock, reserve=balance.reserve, available=balance.available,
            )

    def _get_active_document(self, document_id: int) -> DocumentMove:
        # Отмена и изменение доставки одного документа выполняются по очереди.
        document = self.db.scalar(
            select(DocumentMove).where(DocumentMove.id == document_id).with_for_update()
        )
        if document is None:
            raise NotFoundError("Документ не найден", code="document_not_found")
        if document.is_deleted:
            raise ConflictError(
                "Нельзя изменять документ отмены", code="cannot_modify_reversal"
            )
        # После ожидания блокировки отдельный SELECT видит завершившуюся отмену.
        reversal_id = self.db.scalar(
            select(DocumentMove.id).where(DocumentMove.reversal_of_id == document_id)
        )
        if reversal_id is not None:
            raise ConflictError(
                "Документ уже отменён", code="document_already_cancelled",
                context={"reversal_id": reversal_id},
            )
        return document

    def set_delivery(self, document_id: int, *, is_delivered: bool = True) -> DocumentRead:
        with self._transaction():
            document = self._get_active_document(document_id)
            if document.document_type not in TRANSIT_TYPES:
                raise InvalidOperationError(
                    "Доставка доступна только для перемещения, отправки на ФБО или клиенту",
                    code="invalid_delivery_document",
                )
            if document.is_delivered == is_delivered:
                return self.get_document(document.id)

            # У перемещения есть получатель; у ФБО/FBS его нет.
            # Склады уже проверены при создании документа.
            if document.target_warehouse is not None:
                direction = 1 if is_delivered else -1
                self._apply_stock_changes(
                    {
                        (move.good_id, document.target_warehouse): move.quantity * direction
                        for move in document.stock_moves
                    },
                    check_available=False,
                )
            document.is_delivered = is_delivered
            self.db.flush()
            return self.get_document(document.id)

    def cancel_document(self, document_id: int) -> DocumentRead:
        with self._transaction():
            original = self._get_active_document(document_id)
            reversal = self._record_document(
                kind=DocumentKind(original.document_type),
                source_warehouse=original.source_warehouse,
                target_warehouse=original.target_warehouse,
                quantities={move.good_id: -move.quantity for move in original.stock_moves},
                reversal_of_id=original.id,
                is_delivered=original.is_delivered,
            )
            return self.get_document(reversal.id)

    @staticmethod
    def _validate_warehouses(
        kind: DocumentKind,
        source_warehouse: int | None,
        target_warehouse: int | None,
    ) -> None:
        if kind in SHIPMENT_TYPES:
            valid = source_warehouse is not None and target_warehouse is None
            message = "Для отправки нужен source_warehouse; target_warehouse должен быть null"
        elif kind == DocumentKind.RECEIPT:
            valid = source_warehouse is None and target_warehouse is not None
            message = "Для прихода нужен target_warehouse; source_warehouse должен быть null"
        else:
            valid = (
                source_warehouse is not None
                and target_warehouse is not None
                and source_warehouse != target_warehouse
            )
            message = "Для перемещения нужны два разных склада: source_warehouse и target_warehouse"
        if not valid:
            raise InvalidOperationError(message, code="invalid_warehouses")

    def _lock_balances(self, keys: list[BalanceKey]) -> dict[BalanceKey, StockBalance]:
        balances = {}
        # Создаём и блокируем остатки в одном порядке для всех операций.
        for good_id, warehouse_id in sorted(keys):
            self.db.execute(
                insert(StockBalance)
                .values(good_id=good_id, warehouse_id=warehouse_id)
                .on_conflict_do_nothing(
                    index_elements=[StockBalance.good_id, StockBalance.warehouse_id]
                )
            )
            balances[(good_id, warehouse_id)] = self.db.scalars(
                select(StockBalance)
                .where(
                    StockBalance.good_id == good_id,
                    StockBalance.warehouse_id == warehouse_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            ).one()
        return balances

    def _apply_stock_changes(
        self, changes: dict[BalanceKey, int], *, check_available: bool,
    ) -> None:
        balances = self._lock_balances(list(changes))
        if check_available:
            shortages = [
                {
                    "good_id": good_id, "warehouse_id": warehouse_id,
                    "requested": -change,
                    "available": balances[(good_id, warehouse_id)].available,
                }
                for (good_id, warehouse_id), change in sorted(changes.items())
                if change < 0 and balances[(good_id, warehouse_id)].available < -change
            ]
            if shortages:
                raise ConflictError(
                    "Недостаточно доступного товара на складе",
                    code="insufficient_stock", context={"shortages": shortages},
                )
        for key, change in changes.items():
            balance = balances[key]
            balance.stock += change
            balance.available = balance.stock - balance.reserve

    def _record_document(
        self, *, kind: DocumentKind,
        source_warehouse: int | None, target_warehouse: int | None,
        quantities: dict[int, int], reversal_of_id: int | None = None,
        is_delivered: bool = False,
    ) -> DocumentMove:
        changes: dict[BalanceKey, int] = {}
        for good_id, quantity in quantities.items():
            if source_warehouse is not None:
                changes[(good_id, source_warehouse)] = -quantity
            # При отмене перемещения получатель списывается только после доставки.
            if target_warehouse is not None and (
                kind != DocumentKind.TRANSFER or is_delivered
            ):
                changes[(good_id, target_warehouse)] = quantity
        is_reversal = reversal_of_id is not None
        self._apply_stock_changes(changes, check_available=not is_reversal)
        document = DocumentMove(
            document_type=kind.value,
            source_warehouse=source_warehouse, target_warehouse=target_warehouse,
            is_deleted=is_reversal, is_delivered=is_delivered,
            reversal_of_id=reversal_of_id,
            stock_moves=[
                StockMove(good_id=good_id, quantity=quantity)
                for good_id, quantity in sorted(quantities.items())
            ],
        )
        self.db.add(document)
        self.db.flush()
        return document

    @staticmethod
    def _document_query():
        return select(DocumentMove).options(
            joinedload(DocumentMove.document_type_ref),
            joinedload(DocumentMove.reversal),
            selectinload(DocumentMove.stock_moves).joinedload(StockMove.good),
        )

    @staticmethod
    def _document_response(document: DocumentMove) -> DocumentRead:
        in_transit = (
            document.document_type in TRANSIT_TYPES
            and not document.is_deleted
            and not document.is_delivered
            and document.reversal is None
        )
        return DocumentRead(
            id=document.id, created_at=document.created_at,
            document_type=document.document_type,
            document_type_name=document.document_type_ref.name,
            source_warehouse=document.source_warehouse,
            target_warehouse=document.target_warehouse,
            is_deleted=document.is_deleted, is_delivered=document.is_delivered,
            total_in_transit=sum(move.quantity for move in document.stock_moves) if in_transit else 0,
            reversal_of_id=document.reversal_of_id,
            is_cancelled=document.reversal is not None,
            reversal_id=document.reversal.id if document.reversal else None,
            items=[
                DocumentItemRead(
                    id=move.id, good_id=move.good_id,
                    sku=move.good.sku, name=move.good.name,
                    quantity=move.quantity, in_transit=move.quantity if in_transit else 0,
                )
                for move in document.stock_moves
            ],
        )

    def get_document(self, document_id: int) -> DocumentRead:
        document = self.db.scalar(
            self._document_query()
            .where(DocumentMove.id == document_id)
            .execution_options(populate_existing=True)
        )
        if document is None:
            raise NotFoundError("Документ не найден", code="document_not_found")
        return self._document_response(document)

    def list_documents(
        self, *, document_type: DocumentKind | None = None,
        include_reversals: bool = True,
    ) -> list[DocumentRead]:
        query = self._document_query()
        if document_type is not None:
            query = query.where(DocumentMove.document_type == document_type.value)
        if not include_reversals:
            query = query.where(DocumentMove.is_deleted.is_(False))
        documents = self.db.scalars(query.order_by(DocumentMove.id.desc()))
        return [self._document_response(document) for document in documents]

    def list_stock_balances(self) -> list[StockBalanceRead]:
        # 1. Получаем одну строку «В пути» на товар с суммами ФБО/FBS/перемещений.
        # Считаем до соединения со складами, чтобы количество не умножалось.
        transit = (
            select(
                StockMove.good_id,
                func.sum(StockMove.quantity)
                .filter(DocumentMove.document_type == DocumentKind.SHIPMENT_FBO.value)
                .label("fbo"),
                func.sum(StockMove.quantity)
                .filter(DocumentMove.document_type == DocumentKind.SHIPMENT.value)
                .label("fbs"),
                func.sum(StockMove.quantity)
                .filter(DocumentMove.document_type == DocumentKind.TRANSFER.value)
                .label("transfer"),
            )
            .join(StockMove.document_move)
            .where(
                # Только недоставленные исходные документы без отмены.
                # has() — SQL EXISTS внутри этого же запроса.
                DocumentMove.document_type.in_([kind.value for kind in TRANSIT_TYPES]),
                DocumentMove.is_deleted.is_(False),
                DocumentMove.is_delivered.is_(False),
                ~DocumentMove.reversal.has(),
            )
            .group_by(StockMove.good_id)
            .subquery("transit")
        )

        # 2. Показываем каждый товар на всех складах, даже если строки остатка нет.
        # COALESCE заменяет отсутствующие количества на ноль.
        query = (
            select(
                Good.id.label("good_id"), Good.sku, Good.name.label("good_name"),
                Warehouse.id.label("warehouse_id"), Warehouse.name.label("warehouse_name"),
                func.coalesce(StockBalance.available, 0).label("available"),
                func.coalesce(StockBalance.reserve, 0).label("reserve"),
                func.coalesce(transit.c.fbo, 0).label("fbo"),
                func.coalesce(transit.c.fbs, 0).label("fbs"),
                func.coalesce(transit.c.transfer, 0).label("transfer"),
            )
            .select_from(Good)
            .outerjoin(Warehouse, true())
            .outerjoin(
                StockBalance,
                and_(StockBalance.good_id == Good.id, StockBalance.warehouse_id == Warehouse.id),
            )
            .outerjoin(transit, transit.c.good_id == Good.id)
            .order_by(Good.id, Warehouse.id)
        )

        # 3. Здесь выполняется единственный SELECT. Поля читаем по именам.
        result: dict[int, StockBalanceRead] = {}
        for row in self.db.execute(query).mappings():
            item = result.get(row["good_id"])
            if item is None:
                # «В пути» относится к товару целиком: переносим один раз.
                item = StockBalanceRead(
                    good_id=row["good_id"], sku=row["sku"], name=row["good_name"],
                    total_available=0, total_reserve=0,
                    in_transit_fbo=row["fbo"], in_transit_fbs=row["fbs"],
                    in_transit_transfer=row["transfer"],
                    total_in_transit=row["fbo"] + row["fbs"] + row["transfer"],
                    warehouses=[],
                )
                result[row["good_id"]] = item
            if row["warehouse_id"] is not None:
                item.warehouses.append(WarehouseAvailability(
                    warehouse_id=row["warehouse_id"], name=row["warehouse_name"],
                    available=row["available"], reserve=row["reserve"],
                ))
                item.total_available += row["available"]
                item.total_reserve += row["reserve"]
        return list(result.values())
