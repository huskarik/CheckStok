from fastapi import APIRouter, status

from app.api.deps import Inventory, RecordId
from app.core.document_types import DocumentKind
from app.schemas.inventory import (
    DocumentCreate,
    DocumentDeliveryUpdate,
    DocumentRead,
    DocumentTypeRead,
    ReserveChange,
    ReserveRead,
    StockBalanceRead,
)
from app.services.inventory import InventoryService

router = APIRouter(tags=["Документы и остатки"])


@router.get(
    "/document-types",
    response_model=list[DocumentTypeRead],
    summary="Поддерживаемые типы документов",
)
def list_document_types():
    return InventoryService.get_document_types()


@router.get(
    "/stock-balances",
    response_model=list[StockBalanceRead],
    summary="Остатки, резервы и товары в пути по направлениям",
)
def list_stock_balances(service: Inventory):
    return service.list_stock_balances()


@router.post(
    "/reserves",
    response_model=ReserveRead,
    summary="Зарезервировать товар без документа",
    responses={
        409: {"description": "Недостаточно доступного товара или нарушена ссылка БД"},
    },
)
def create_reserve(data: ReserveChange, service: Inventory):
    return service.create_reserve(data)


@router.post(
    "/reserves/release",
    response_model=ReserveRead,
    summary="Снять резерв товара без документа",
    responses={
        409: {"description": "Количество превышает резерв или нарушена ссылка БД"},
    },
)
def release_reserve(data: ReserveChange, service: Inventory):
    return service.release_reserve(data)


@router.get("/documents", response_model=list[DocumentRead], summary="Журнал документов")
def list_documents(
    service: Inventory,
    document_type: DocumentKind | None = None,
    include_reversals: bool = True,
):
    return service.list_documents(
        document_type=document_type,
        include_reversals=include_reversals,
    )


@router.post(
    "/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать и провести документ",
    responses={
        409: {"description": "Недостаточно доступного товара или нарушены ограничения БД"},
        422: {"description": "Неверные склады, количества или флаг FBO"},
    },
)
def create_document(data: DocumentCreate, service: Inventory):
    return service.create_document(data)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentRead,
    summary="Получить документ с товарами",
    responses={404: {"description": "Документ не найден"}},
)
def get_document(document_id: RecordId, service: Inventory):
    return service.get_document(document_id)


@router.post(
    "/documents/{document_id}/delivered",
    response_model=DocumentRead,
    summary="Установить или снять отметку доставки",
    description=(
        "is_delivered=true подтверждает доставку, false возвращает товары в путь. "
        "У перемещения подтверждение пополняет склад-получатель, снятие списывает "
        "его даже при нехватке остатка. У отправок ФБО/FBS меняется только «В пути». "
        "Новых документов и движений нет. Повтор того же значения безопасен. "
        "Запрос без тела означает подтверждение доставки."
    ),
    responses={
        404: {"description": "Документ не найден"},
        409: {"description": "Документ отменён или сам является отменой"},
        422: {"description": "Тип документа не предполагает доставку"},
    },
)
def set_delivery(
    document_id: RecordId,
    service: Inventory,
    data: DocumentDeliveryUpdate | None = None,
):
    return service.set_delivery(
        document_id, is_delivered=data.is_delivered if data is not None else True
    )


@router.delete(
    "/documents/{document_id}",
    response_model=DocumentRead,
    summary="Отменить документ обратным движением",
    description=(
        "Возвращает новый документ с is_deleted=true, reversal_of_id исходного "
        "документа и отрицательными количествами. Исходный документ сохраняется. "
        "Отмена допускает отрицательные остатки. Повторная отмена запрещена."
    ),
    responses={
        404: {"description": "Документ не найден"},
        409: {"description": "Документ уже отменён или сам является отменой"},
    },
)
def cancel_document(document_id: RecordId, service: Inventory):
    return service.cancel_document(document_id)
