import { api } from "./api.js";
import { byId, button, cell, element, fillSelect, notice, number, numberClass, tableState } from "./ui.js";

export function createBalancesView(context) {
  let loading = false;
  let saving = false;
  let releasing = false;
  let selectedGood = null;
  const body = byId("balances-body");
  const editor = byId("reserve-editor");
  const form = byId("reserve-form");
  const warehouseSelect = byId("reserve-warehouse");
  const quantityInput = byId("reserve-quantity");
  const selectedWarehouse = () => selectedGood?.warehouses.find((item) => item.warehouse_id === Number(warehouseSelect.value));
  const quantityLimit = () => (releasing ? selectedWarehouse()?.reserve : selectedWarehouse()?.available) ?? 0;

  function controls() {
    for (const item of body.querySelectorAll("button")) {
      item.disabled = loading || saving || item.dataset.noWarehouses === "true" || item.dataset.noReserve === "true";
    }
    byId("reserve-fields").disabled = saving;
    byId("reserve-close").disabled = saving;
    byId("reserve-submit").disabled = saving || quantityLimit() <= 0;
    byId("reserve-submit").textContent = saving
      ? (releasing ? "Снятие резерва…" : "Резервирование…")
      : (releasing ? "Снять резерв" : "Зарезервировать");
  }

  function metricCells(row, available, reserve, total = false) {
    for (const [index, value] of [available, reserve].entries()) {
      cell(row, number(value), `metric ${numberClass(value)}${index === 0 ? " group-start" : ""}${total ? " metric-total" : ""}`);
    }
  }

  function render(rows) {
    const warehouses = rows[0]?.warehouses || [];
    const groups = element("tr");
    const metrics = element("tr");
    for (const title of ["Артикул", "Наименование товара"]) {
      const th = element("th", "", title);
      th.scope = "col";
      th.rowSpan = 2;
      groups.append(th);
    }
    for (const [index, title] of ["Всего", ...warehouses.map((item) => item.name)].entries()) {
      const group = element("th", `warehouse-group${index === 0 ? " metric-total" : ""}`, title);
      group.scope = "colgroup";
      group.colSpan = 2;
      groups.append(group);
      for (const [metricIndex, label] of ["Доступно", "В резерве"].entries()) {
        const th = element("th", `metric${metricIndex === 0 ? " group-start" : ""}${index === 0 ? " metric-total" : ""}`, label);
        th.scope = "col";
        metrics.append(th);
      }
      if (index === 0) {
        const transit = element("th", "warehouse-group metric-total", "В пути");
        transit.scope = "colgroup";
        transit.colSpan = 3;
        transit.title = "Только неотменённые документы, по которым товары ещё не доехали";
        groups.append(transit);
        for (const [directionIndex, label] of ["На ФБО", "Клиентам (FBS)", "Между складами"].entries()) {
          const th = element("th", `metric metric-total${directionIndex === 0 ? " group-start" : ""}`, label);
          th.scope = "col";
          metrics.append(th);
        }
      }
    }
    const actions = element("th", "", "Действия");
    actions.scope = "col";
    actions.rowSpan = 2;
    groups.append(actions);
    byId("balances-head").replaceChildren(groups, metrics);
    body.replaceChildren();
    for (const item of rows) {
      const row = element("tr");
      cell(row, item.sku, "sku");
      cell(row, item.name);
      metricCells(row, item.total_available, item.total_reserve, true);
      for (const [index, value] of [item.in_transit_fbo, item.in_transit_fbs, item.in_transit_transfer].entries()) {
        cell(row, number(value), `metric metric-total ${numberClass(value)}${index === 0 ? " group-start" : ""}`);
      }
      const byWarehouse = new Map(item.warehouses.map((warehouse) => [warehouse.warehouse_id, warehouse]));
      for (const warehouse of warehouses) {
        const balance = byWarehouse.get(warehouse.warehouse_id);
        metricCells(row, balance?.available ?? 0, balance?.reserve ?? 0);
      }
      const reserveButton = button("Зарезервировать товар", () => openReserve(item), "button small secondary");
      reserveButton.dataset.noWarehouses = String(item.warehouses.length === 0);
      reserveButton.setAttribute("aria-label", `Зарезервировать товар: ${item.name}`);
      const releaseButton = button("Снять резерв", () => openReserve(item, true), "button small secondary");
      releaseButton.dataset.noReserve = String(item.total_reserve <= 0);
      releaseButton.dataset.noWarehouses = String(item.warehouses.length === 0);
      releaseButton.setAttribute("aria-label", `Снять резерв: ${item.name}`);
      const actions = element("div", "reserve-actions");
      actions.append(reserveButton, releaseButton);
      cell(row, "", "balance-actions").append(actions);
      body.append(row);
    }
  }

  function updateReserveHint() {
    const warehouse = selectedWarehouse();
    byId("reserve-available").textContent = warehouse
      ? `Доступно: ${number(warehouse.available)} шт. · Уже в резерве: ${number(warehouse.reserve)} шт.`
      : "Выберите склад.";
    quantityInput.max = String(Math.max(0, quantityLimit()));
    quantityInput.disabled = quantityLimit() <= 0;
    controls();
  }

  function openReserve(good, release = false) {
    if (loading || saving || !good.warehouses.length) return;
    selectedGood = good;
    releasing = release;
    form.reset();
    byId("reserve-title").textContent = releasing ? "Снять резерв" : "Зарезервировать товар";
    byId("reserve-product-name").textContent = good.name;
    byId("reserve-product-sku").textContent = good.sku;
    fillSelect(
      warehouseSelect,
      good.warehouses.map((item) => ({ id: item.warehouse_id, name: item.name })),
      "Выберите склад",
      (warehouse) => warehouse.name,
    );
    const preferred = good.warehouses.find((item) => (releasing ? item.reserve : item.available) > 0) || good.warehouses[0];
    warehouseSelect.value = String(preferred.warehouse_id);
    quantityInput.value = "1";
    notice("reserve-error");
    updateReserveHint();
    editor.showModal();
    warehouseSelect.focus();
  }

  warehouseSelect.addEventListener("change", updateReserveHint);
  byId("reserve-close").addEventListener("click", () => editor.close());
  editor.addEventListener("cancel", (event) => { if (saving) event.preventDefault(); });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (saving || !selectedGood) return;
    const warehouse = selectedWarehouse();
    const quantity = quantityInput.valueAsNumber;
    if (!warehouse || !Number.isSafeInteger(quantity) || quantity <= 0 || quantity > quantityLimit()) {
      notice("reserve-error", releasing
        ? "Укажите положительное целое количество не больше резерва на выбранном складе."
        : "Укажите положительное целое количество не больше доступного на выбранном складе.");
      return;
    }
    saving = true;
    context.setBusy(true);
    controls();
    notice("reserve-error");
    try {
      await api(releasing ? "reserves/release" : "reserves", { method: "POST", body: {
        good_id: selectedGood.good_id, warehouse_id: warehouse.warehouse_id, quantity,
      } });
      editor.close();
      context.notify(releasing
        ? `С товара «${selectedGood.name}» снят резерв: ${number(quantity)} шт., ${warehouse.name}.`
        : `Товар «${selectedGood.name}» зарезервирован: ${number(quantity)} шт., ${warehouse.name}.`);
      await context.reload();
    } catch (error) {
      const shortage = error.context?.shortages?.[0];
      if (shortage) warehouse.available = shortage.available;
      let message = shortage ? `${error.message}. Сейчас доступно: ${number(shortage.available)} шт.` : error.message;
      if (error.code === "insufficient_reserve") {
        warehouse.reserve = error.context.reserve;
        warehouse.available = error.context.available;
        message = `${error.message}. Сейчас в резерве: ${number(warehouse.reserve)} шт.`;
      }
      notice("reserve-error", message);
      updateReserveHint();
    } finally {
      saving = false;
      context.setBusy(false);
      controls();
    }
  });

  return {
    async load({ signal }) {
      loading = true;
      render([]);
      byId("balances-count").textContent = "";
      notice("balances-error");
      tableState("balances", "Загрузка остатков…", true);
      controls();
      try {
        const rows = await api("stock-balances", { signal });
        if (signal.aborted) return;
        render(rows);
        byId("balances-count").textContent = `Всего товаров: ${number(rows.length)}`;
        tableState("balances", rows.length ? "" : "Товаров пока нет. Добавьте их в справочнике «Товары».");
      } catch (error) {
        if (signal.aborted) return;
        notice("balances-error", error.message);
        tableState("balances", "Не удалось загрузить остатки. Нажмите «Обновить», чтобы повторить.");
      } finally {
        if (!signal.aborted) { loading = false; controls(); }
      }
    },
  };
}
