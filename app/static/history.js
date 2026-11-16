import { api } from "./api.js";
import {
  byId, button, cell, confirmAction, dateTime, documentStatus, documentTypeClass,
  element, notice, number, numberClass, tableState,
} from "./ui.js";

export function createHistoryView(context) {
  let rows = [];
  let loading = false;
  let saving = false;
  let warehouseNames = new Map();
  let detailController;
  const body = byId("history-body");
  const details = byId("document-details");
  const warehouseName = (id) => id === null ? "—" : warehouseNames.get(id) || `Склад #${id}`;
  const hasDelivery = (record) => ["transfer", "shipment", "shipment_fbo"].includes(record.document_type) && !record.is_deleted;

  function controls() {
    byId("history-type").disabled = saving;
    byId("history-reversals").disabled = saving;
    for (const item of body.querySelectorAll("button")) item.disabled = loading || saving;
    for (const item of byId("document-details-actions").querySelectorAll("button")) item.disabled = saving;
    for (const item of byId("document-details-body").querySelectorAll("input[data-delivery]")) {
      item.disabled = saving || item.dataset.cancelled === "true";
    }
    byId("document-details-close").disabled = saving;
  }

  function render() {
    body.replaceChildren();
    for (const record of rows) {
      const row = element("tr");
      const title = cell(row, "");
      title.append(element("span", `badge ${documentTypeClass(record.document_type)}`, record.document_type_name));
      title.append(element("span", "operation-id", `№${record.id}`));
      cell(row, dateTime(record.created_at), "date-cell");
      cell(row, warehouseName(record.source_warehouse));
      cell(row, warehouseName(record.target_warehouse));
      cell(row, number(record.items.length), "numeric");
      cell(row, "").append(documentStatus(record));
      const actions = element("div", "row-actions");
      const open = button("Открыть", () => openDocument(record.id));
      open.setAttribute("aria-label", `Открыть операцию №${record.id}`);
      actions.append(open);
      if (!record.is_deleted && !record.is_cancelled) {
        const cancel = button("Отменить", () => cancelDocument(record), "text-button danger");
        cancel.setAttribute("aria-label", `Отменить операцию №${record.id}`);
        actions.append(cancel);
      }
      cell(row, "").append(actions);
      body.append(row);
    }
  }

  async function cancelDocument(record) {
    if (saving || loading || record.is_deleted || record.is_cancelled) return;
    const confirmed = await confirmAction(
      `Отменить операцию №${record.id}?`,
      `«${record.document_type_name}»: будет создана обратная операция и пересчитаны остатки. Обе записи сохранятся в истории.`,
      "Отменить операцию",
    );
    if (!confirmed) return;
    if (details.open) details.close();
    saving = true;
    context.setBusy(true);
    controls();
    notice("history-error");
    try {
      const reversal = await api(`documents/${record.id}`, { method: "DELETE" });
      context.notify(`Операция №${record.id} отменена. Создана обратная операция №${reversal.id}. Остатки обновлены.`);
      await context.reload();
    } catch (error) {
      notice("history-error", error.message);
      // Перечитываем статус, если документ уже успел отменить другой пользователь.
      if (error.code === "document_already_cancelled") {
        context.notify(error.message, null, "neutral");
        await context.reload();
      }
    } finally {
      saving = false;
      context.setBusy(false);
      controls();
    }
  }

  async function setDelivery(record, isDelivered, checkbox) {
    if (saving || loading || !hasDelivery(record) || record.is_cancelled) {
      checkbox.checked = record.is_delivered;
      return;
    }
    saving = true;
    context.setBusy(true);
    controls();
    notice("document-details-error");
    try {
      const updated = await api(`documents/${record.id}/delivered`, {
        method: "POST", body: { is_delivered: isDelivered },
      });
      renderDocument(updated);
      context.notify(isDelivered
        ? `Товары операции №${record.id} доехали. Остатки обновлены.`
        : `Подтверждение доставки операции №${record.id} снято. Товары снова в пути.`);
      await context.reload();
    } catch (error) {
      checkbox.checked = record.is_delivered;
      notice("document-details-error", error.message);
      if (error.code === "document_already_cancelled") {
        details.close();
        context.notify(error.message, null, "neutral");
        await context.reload();
      }
    } finally {
      saving = false;
      context.setBusy(false);
      controls();
    }
  }

  function renderDocument(record) {
    byId("document-details-title").textContent = `Операция №${record.id}`;
    const content = byId("document-details-body");
    content.replaceChildren();
    const meta = element("dl", "document-meta");
    const metadata = [
      ["Тип операции", record.document_type_name],
      ["Дата и время, МСК", dateTime(record.created_at)],
      ["Статус", null],
      ["Склад-источник", warehouseName(record.source_warehouse)],
      ["Склад-получатель", warehouseName(record.target_warehouse)],
      ["Товарных позиций", number(record.items.length)],
    ];
    if (hasDelivery(record)) {
      metadata.push(["Направление", record.document_type === "transfer" ? "Между ФФ" : record.document_type === "shipment_fbo" ? "На ФБО" : "Клиенту (FBS)"]);
      metadata.push(["В пути, шт.", number(record.total_in_transit)]);
      metadata.push(["Доставка", record.is_cancelled ? "Документ отменён" : record.is_delivered ? "Товары доехали" : "В пути"]);
    }
    for (const [label, value] of metadata) {
      const item = element("div");
      item.append(element("dt", "", label));
      const valueNode = element("dd", "", value ?? "");
      if (value === null) valueNode.append(documentStatus(record));
      item.append(valueNode);
      meta.append(item);
    }
    content.append(meta);
    if (hasDelivery(record)) {
      const label = element("label", "checkbox-field delivery-toggle");
      const checkbox = element("input");
      checkbox.type = "checkbox";
      checkbox.checked = record.is_delivered;
      checkbox.disabled = record.is_cancelled;
      checkbox.dataset.delivery = "true";
      checkbox.dataset.cancelled = String(record.is_cancelled);
      checkbox.addEventListener("change", () => setDelivery(record, checkbox.checked, checkbox));
      const text = element("span");
      text.append(element("strong", "", "Товары доехали"));
      text.append(element("small", "", record.is_cancelled
        ? "Доставка отменённой операции недоступна для изменения."
        : record.document_type === "transfer"
          ? "Галочка зачисляет товар получателю. Снятие возвращает его в путь; остаток получателя может стать отрицательным."
          : "Галочка исключает товары из общего количества «В пути». Её можно снять."));
      label.append(checkbox, text);
      content.append(label);
    }
    const scroll = element("div", "table-scroll");
    const table = element("table");
    const head = element("thead");
    const headRow = element("tr");
    const columns = ["Артикул", "Наименование товара", "Количество, шт."];
    if (hasDelivery(record)) columns.push("В пути, шт.");
    for (const title of columns) {
      const th = element("th", "", title);
      th.scope = "col";
      headRow.append(th);
    }
    head.append(headRow);
    const tableBody = element("tbody");
    for (const item of record.items) {
      const row = element("tr");
      cell(row, item.sku, "sku");
      cell(row, item.name);
      cell(row, number(item.quantity), `numeric ${numberClass(item.quantity)}`);
      if (hasDelivery(record)) cell(row, number(item.in_transit), "numeric");
      tableBody.append(row);
    }
    table.append(head, tableBody);
    scroll.append(table);
    content.append(scroll);
    const actions = byId("document-details-actions");
    actions.replaceChildren();
    if (record.reversal_of_id !== null) {
      actions.append(button(`Исходная операция №${record.reversal_of_id} →`, () => openDocument(record.reversal_of_id)));
    } else if (record.reversal_id !== null) {
      actions.append(button(`Обратная операция №${record.reversal_id} →`, () => openDocument(record.reversal_id)));
    }
    if (!record.is_deleted && !record.is_cancelled) {
      actions.append(button("Отменить операцию", () => cancelDocument(record), "button secondary danger"));
    }
    actions.append(button("Закрыть", () => details.close(), "button secondary"));
  }

  async function openDocument(id) {
    if (saving || loading) return;
    detailController?.abort();
    const controller = new AbortController();
    detailController = controller;
    byId("document-details-title").textContent = `Операция №${id}`;
    byId("document-details-body").replaceChildren(element("p", "muted", "Загрузка операции…"));
    byId("document-details-actions").replaceChildren();
    notice("document-details-error");
    if (!details.open) details.showModal();
    try {
      const record = await api(`documents/${id}`, { signal: controller.signal });
      if (!controller.signal.aborted) renderDocument(record);
    } catch (error) {
      if (controller.signal.aborted) return;
      byId("document-details-body").replaceChildren();
      notice("document-details-error", error.message);
    }
  }

  byId("document-details-close").addEventListener("click", () => details.close());
  details.addEventListener("close", () => detailController?.abort());
  details.addEventListener("cancel", (event) => { if (saving) event.preventDefault(); });
  for (const id of ["history-type", "history-reversals"]) {
    byId(id).addEventListener("change", () => {
      if (saving) return;
      void context.reload();
    });
  }
  return {
    async load({ signal }) {
      loading = true;
      rows = [];
      render();
      byId("history-count").textContent = "";
      controls();
      notice("history-error");
      tableState("history", "Загрузка истории операций…", true);
      try {
        const filters = new URLSearchParams({ include_reversals: byId("history-reversals").checked });
        if (byId("history-type").value) filters.set("document_type", byId("history-type").value);
        const [data, warehouses] = await Promise.all([
          api(`documents?${filters}`, { signal }), api("warehouses", { signal }),
        ]);
        if (signal.aborted) return;
        warehouseNames = new Map(warehouses.map((warehouse) => [warehouse.id, warehouse.name]));
        rows = data;
        render();
        byId("history-count").textContent = `Всего документов: ${number(rows.length)}`;
        tableState("history", rows.length ? "" : "Операций с такими условиями пока нет. Создайте новую операцию или измените фильтр.");
      } catch (error) {
        if (signal.aborted) return;
        notice("history-error", error.message);
        tableState("history", "История не загружена. Нажмите «Обновить», чтобы повторить.");
      } finally {
        if (!signal.aborted) { loading = false; controls(); }
      }
    },
  };
}
