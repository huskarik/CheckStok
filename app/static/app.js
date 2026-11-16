import { createBalancesView } from "./balances.js";
import { createOperationsView } from "./operations.js";
import { createHistoryView } from "./history.js";
import { createCatalogsView } from "./catalogs.js";
import { byId, button, notice } from "./ui.js";

const pages = {
  balances: { title: "Текущие остатки", description: "Остатки и резервы по складам. В пути: на ФБО, клиентам по FBS и между складами.", breadcrumb: "Остатки", panel: "balances" },
  operations: { title: "Новая операция", description: "Приход, отправка и перемещение товаров между складами.", breadcrumb: "Новая операция", panel: "operations" },
  history: { title: "История операций", description: "Все проведённые документы и их обратные операции.", breadcrumb: "История операций", panel: "history" },
  goods: { title: "Товары", description: "Артикулы и наименования товаров компании.", breadcrumb: "Товары", panel: "catalogs", create: "＋ Добавить товар" },
  warehouses: { title: "Склады", description: "Склады, между которыми движутся товары.", breadcrumb: "Склады", panel: "catalogs", create: "＋ Добавить склад" },
};
let current = "balances";
let controller;
let busy = false;
const navigation = [...document.querySelectorAll("[data-view]")];

const context = {
  reload: () => loadCurrent(),
  navigate,
  setBusy(value) {
    busy = value;
    for (const item of navigation) item.disabled = value;
    byId("refresh-button").disabled = value;
    byId("primary-action").disabled = value;
  },
  notify(message, link = null, kind = "success") {
    byId("notification").className = `notice ${kind}`;
    notice("notification", message);
    if (link) byId("notification").append(button(link.label, () => navigate(link.view)));
  },
};
const catalogs = createCatalogsView(context);
const views = {
  balances: createBalancesView(context),
  operations: createOperationsView(context),
  history: createHistoryView(context),
  goods: catalogs,
  warehouses: catalogs,
};

function navigate(name) {
  if (busy) return;
  for (const id of ["confirm-dialog", "catalog-editor", "document-details", "reserve-editor"]) {
    const dialog = byId(id);
    if (dialog.open) { dialog.returnValue = "cancel"; dialog.close(); }
  }
  current = pages[name] ? name : "balances";
  history.replaceState(null, "", `#${current}`);
  const page = pages[current];
  for (const item of navigation) {
    if (item.dataset.view === current) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  }
  for (const section of ["balances", "operations", "history", "catalogs"]) {
    byId(`view-${section}`).hidden = page.panel !== section;
  }
  byId("page-title").textContent = page.title;
  byId("page-description").textContent = page.description;
  byId("breadcrumb").textContent = page.breadcrumb;
  document.title = `${page.title} — CheckStock`;
  byId("primary-action").hidden = current === "operations";
  byId("primary-action").textContent = page.create || "＋ Новая операция";
  byId("refresh-button").hidden = current === "operations";
  notice("notification");
  void loadCurrent();
}

async function loadCurrent() {
  controller?.abort();
  controller = new AbortController();
  const signal = controller.signal;
  try {
    await views[current].load({ section: current, signal });
  } catch (error) {
    if (signal.aborted) return;
    byId("notification").className = "notice error";
    notice("notification", error.message);
  }
}

for (const item of navigation) item.addEventListener("click", () => navigate(item.dataset.view));
byId("refresh-button").addEventListener("click", () => { if (!busy) void loadCurrent(); });
byId("primary-action").addEventListener("click", () => {
  if (busy) return;
  if (pages[current].panel === "catalogs") catalogs.openEditor();
  else navigate("operations");
});
window.addEventListener("hashchange", () => {
  if (busy) history.replaceState(null, "", `#${current}`);
  else navigate(location.hash.slice(1));
});
byId("today-label").textContent = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Moscow",
}).format(new Date());
navigate(location.hash.slice(1));
