import { api } from "./api.js";
import { byId, button, cell, confirmAction, element, notice, number, tableState } from "./ui.js";

const config = {
  goods: { create: "Добавить товар", edit: "Изменить товар", noun: "товар", empty: "Товаров пока нет. Добавьте первый товар." },
  warehouses: { create: "Добавить склад", edit: "Изменить склад", noun: "склад", empty: "Складов пока нет. Добавьте первый склад." },
};

export function createCatalogsView(context) {
  let catalog = "goods";
  let rows = [];
  let loading = false;
  let saving = false;
  let editId = null;
  const editor = byId("catalog-editor");
  const form = byId("catalog-form");
  const body = byId("catalog-body");

  function controls() {
    for (const item of body.querySelectorAll("button")) item.disabled = loading || saving;
    byId("catalog-fields").disabled = saving;
    byId("catalog-save").disabled = saving;
    byId("catalog-editor-close").disabled = saving;
    byId("catalog-save").textContent = saving ? "Сохранение…" : "Сохранить";
  }

  function render() {
    const head = element("tr");
    for (const title of catalog === "goods" ? ["ID", "Артикул", "Наименование", "Действия"] : ["ID", "Наименование", "Действия"]) {
      const th = element("th", "", title);
      th.scope = "col";
      head.append(th);
    }
    byId("catalog-head").replaceChildren(head);
    body.replaceChildren();
    for (const record of rows) {
      const row = element("tr");
      cell(row, `#${record.id}`, "reference-id");
      if (catalog === "goods") cell(row, record.sku, "sku");
      cell(row, record.name);
      const actions = element("div", "row-actions");
      const edit = button("Изменить", () => openEditor(record));
      const remove = button("Удалить", () => removeRecord(record), "text-button danger");
      edit.setAttribute("aria-label", `Изменить: ${record.name}`);
      remove.setAttribute("aria-label", `Удалить: ${record.name}`);
      actions.append(edit, remove);
      cell(row, "").append(actions);
      body.append(row);
    }
  }

  function openEditor(record = null) {
    if (saving) return;
    editId = record?.id ?? null;
    form.reset();
    const isGood = catalog === "goods";
    byId("catalog-sku-field").hidden = !isGood;
    byId("catalog-sku").required = isGood;
    byId("catalog-sku").disabled = !isGood;
    byId("catalog-sku").value = record?.sku || "";
    byId("catalog-name").value = record?.name || "";
    byId("catalog-editor-title").textContent = record ? config[catalog].edit : config[catalog].create;
    notice("catalog-form-error");
    controls();
    editor.showModal();
    (isGood ? byId("catalog-sku") : byId("catalog-name")).focus();
  }

  async function removeRecord(record) {
    if (saving || loading) return;
    const confirmed = await confirmAction(
      `Удалить ${config[catalog].noun}?`,
      `«${record.name}» будет удалён из справочника. Записи, связанные с движениями или остатками, удалить нельзя.`,
      "Удалить",
    );
    if (!confirmed) return;
    saving = true;
    context.setBusy(true);
    controls();
    notice("catalog-error");
    try {
      await api(`${catalog}/${record.id}`, { method: "DELETE" });
      context.notify("Запись удалена из справочника.");
      await context.reload();
    } catch (error) {
      notice("catalog-error", error.message);
    } finally {
      saving = false;
      context.setBusy(false);
      controls();
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (saving) return;
    const data = { name: byId("catalog-name").value.trim() };
    if (catalog === "goods") data.sku = byId("catalog-sku").value.trim();
    if (!data.name || (catalog === "goods" && !data.sku)) {
      notice("catalog-form-error", "Заполните поля: значение не может состоять из пробелов.");
      return;
    }
    saving = true;
    context.setBusy(true);
    controls();
    notice("catalog-form-error");
    try {
      await api(editId === null ? catalog : `${catalog}/${editId}`, {
        method: editId === null ? "POST" : "PATCH", body: data,
      });
      editor.close();
      context.notify(editId === null ? "Запись добавлена в справочник." : "Изменения сохранены.");
      await context.reload();
    } catch (error) {
      notice("catalog-form-error", error.message);
    } finally {
      saving = false;
      context.setBusy(false);
      controls();
    }
  });
  byId("catalog-editor-close").addEventListener("click", () => editor.close());
  editor.addEventListener("cancel", (event) => { if (saving) event.preventDefault(); });
  return {
    openEditor,
    async load({ section, signal }) {
      catalog = section;
      loading = true;
      rows = [];
      render();
      byId("catalog-count").textContent = "";
      notice("catalog-error");
      tableState("catalog", "Загрузка справочника…", true);
      controls();
      try {
        const data = await api(catalog, { signal });
        if (signal.aborted) return;
        rows = data;
        render();
        byId("catalog-count").textContent = `Всего записей: ${number(rows.length)}`;
        tableState("catalog", rows.length ? "" : config[catalog].empty);
      } catch (error) {
        if (signal.aborted) return;
        notice("catalog-error", error.message);
        tableState("catalog", "Справочник не загружен. Нажмите «Обновить», чтобы повторить.");
      } finally {
        if (!signal.aborted) { loading = false; controls(); }
      }
    },
  };
}
