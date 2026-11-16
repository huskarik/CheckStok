from enum import StrEnum


class DocumentKind(StrEnum):
    SHIPMENT = "shipment"
    SHIPMENT_FBO = "shipment_fbo"
    RECEIPT = "receipt"
    TRANSFER = "transfer"


DOCUMENT_TYPE_NAMES: dict[DocumentKind, str] = {
    DocumentKind.SHIPMENT: "Отправка",
    DocumentKind.SHIPMENT_FBO: "Отправка на ФБО",
    DocumentKind.RECEIPT: "Приход",
    DocumentKind.TRANSFER: "Перемещение",
}

SHIPMENT_TYPES = frozenset({DocumentKind.SHIPMENT, DocumentKind.SHIPMENT_FBO})
TRANSIT_TYPES = SHIPMENT_TYPES | {DocumentKind.TRANSFER}
