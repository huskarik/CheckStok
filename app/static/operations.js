import { api } from "./api.js";
import { byId, element, fillSelect, notice, number } from "./ui.js";

const names = { receipt: "Приход", shipment: "Отправка клиенту (FBS)", transfer: "Перемещение" };

export function createOperationsView(context) {
  let goods = [];
  let warehouses = [];
  let saving = false;
  let ready = false;
  const form = byId("operation-form");
  const items = byId("operation-items");
  const source = byId("operation-source");
  const target = byId("operation-target");
  const type = () => form.elements.operation_type.value;
  const warehouseName = (id) => warehouses.find((item) => item.id === Number(id))?.name || "Выберите склад";

  function updateSummary() {
    const kind = type();
    const ids = new Set();
    let total = 0;
    for (const row of items.children) {
      const id = row.querySelector(".item-good").value;
      const quantity = row.querySelector(".item-quantity").valueAsNumber;
      if (id) ids.add(id);
      if (id && Number.isSafeInteger(quantity) && quantity > 0) total += quantity;
    }
    byId("operation-summary-type").textContent = kind === "shipment" && byId("operation-fbo").checked ? "Отправка на ФБО" : names[kind];
    byId("operation-summary-source").textContent = kind === "receipt" ? "Поступление товара" : warehouseName(source.value);
    byId("operation-summary-target").textContent = kind === "shipment" ? (byId("operation-fbo").checked ? "Склад маркетплейса (ФБО)" : "Клиент (FBS)") : warehouseName(target.value);
    byId("operation-summary-count").textContent = number(ids.size);
    byId("operation-summary-quantity").textContent = number(total);
  }

  function configureType() {
    const kind = type();
    const hasSource = kind !== "receipt";
    const hasTarget = kind !== "shipment";
    byId("operation-source-field").hidden = !hasSource;
    byId("operation-target-field").hidden = !hasTarget;
    source.required = hasSource;
    target.required = hasTarget;
    source.disabled = !hasSource;
    target.disabled = !hasTarget;
    if (!hasSource) source.value = "";
    if (!hasTarget) target.value = "";
    byId("operation-fbo-field").hidden = kind !== "shipment";
    if (kind !== "shipment") byId("operation-fbo").checked = false;
    byId("operation-effect").textContent = kind === "receipt"
      ? "Количество товаров увеличится на выбранном складе."
      : kind === "transfer"
        ? "Товары спишутся с источника и будут в пути. Получатель пополнится после подтверждения доставки в документе."
        : "Товары спишутся с выбранного склада. Проверяется доступное количество.";
    updateSummary();
  }

  function addItem() {
    const row = element("div", "line-item");
    const select = element("select", "item-good");
    select.required = true;
    select.setAttribute("aria-label", "Товар");
    fillSelect(select, goods, "Выберите товар", (good) => `${good.sku} — ${good.name}`);
    const quantity = element("input", "item-quantity");
    quantity.type = "number";
    quantity.min = "1";
    quantity.step = "1";
    quantity.value = "1";
    quantity.required = true;
    quantity.setAttribute("aria-label", "Количество товара в штуках");
    const remove = element("button", "remove-line", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", "Убрать товар из операции");
    remove.addEventListener("click", () => {
      if (saving) return;
      row.remove();
      if (!items.children.length) addItem();
      updateSummary();
    });
    row.append(select, quantity, remove);
    items.append(row);
    updateSummary();
    return select;
  }

  function controls() {
    byId("operation-fields").disabled = !ready || saving;
    byId("operation-submit").textContent = saving ? "Проведение операции…" : "Провести операцию";
  }

  function errorMessage(error) {
    const shortages = error.context?.shortages;
    if (!shortages?.length) return error.message;
    return [error.message, ...shortages.map((item) => {
      const good = goods.find((record) => record.id === item.good_id);
      return `${good ? `${good.sku} — ${good.name}` : `Товар #${item.good_id}`}, ${warehouseName(item.warehouse_id)}: доступно ${number(item.available)}, требуется ${number(item.requested)}.`;
    })].join("\n");
  }

  byId("add-operation-item").addEventListener("click", () => { if (!saving) addItem().focus(); });
  form.addEventListener("input", updateSummary);
  form.addEventListener("change", (event) => {
    if (event.target.name === "operation_type") configureType();
    else updateSummary();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!ready || saving) return;
    notice("operations-error");
    const kind = type();
    if (kind === "transfer" && source.value === target.value) {
      notice("operations-error", "Для перемещения выберите два разных склада.");
      target.focus();
      return;
    }
    const lines = [...items.children].map((row) => ({
      good_id: Number(row.querySelector(".item-good").value),
      quantity: row.querySelector(".item-quantity").valueAsNumber,
    }));
    if (!lines.length || lines.some((item) => !item.good_id || !Number.isSafeInteger(item.quantity) || item.quantity <= 0)) {
      notice("operations-error", "Выберите товары и укажите положительное целое количество для каждой строки.");
      return;
    }
    const payload = {
      document_type: kind,
      source_warehouse: kind === "receipt" ? null : Number(source.value),
      target_warehouse: kind === "shipment" ? null : Number(target.value),
      fbo: kind === "shipment" && byId("operation-fbo").checked,
      items: lines,
    };
    saving = true;
    context.setBusy(true);
    controls();
    try {
      const record = await api("documents", { method: "POST", body: payload });
      context.notify(`Операция №${record.id} «${record.document_type_name}» проведена. Остатки обновлены.`, { label: "Открыть историю →", view: "history" });
      items.replaceChildren();
      addItem();
    } catch (error) {
      notice("operations-error", errorMessage(error));
    } finally {
      saving = false;
      context.setBusy(false);
      controls();
    }
  });

  return {
    async load({ signal }) {
      ready = false;
      controls();
      notice("operations-error");
      notice("operations-status", "Загрузка товаров и складов…");
      try {
        const [newGoods, newWarehouses] = await Promise.all([
          api("goods", { signal }), api("warehouses", { signal }),
        ]);
        if (signal.aborted) return;
        goods = newGoods;
        warehouses = newWarehouses;
        fillSelect(source, warehouses, "Выберите склад", (warehouse) => warehouse.name);
        fillSelect(target, warehouses, "Выберите склад", (warehouse) => warehouse.name);
        for (const select of items.querySelectorAll(".item-good")) {
          fillSelect(select, goods, "Выберите товар", (good) => `${good.sku} — ${good.name}`);
        }
        if (!items.children.length) addItem();
        ready = goods.length > 0 && warehouses.length > 0;
        notice("operations-status", ready ? "" : "Сначала добавьте хотя бы один товар и один склад в справочниках.");
        configureType();
      } catch (error) {
        if (signal.aborted) return;
        notice("operations-status");
        notice("operations-error", `${error.message} Перейдите в раздел повторно, чтобы загрузить справочники.`);
      } finally {
        if (!signal.aborted) controls();
      }
    },
  };
}
