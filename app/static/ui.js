export const byId = (id) => document.getElementById(id);
const numberFormat = new Intl.NumberFormat("ru-RU");
const dateFormat = new Intl.DateTimeFormat("ru-RU", {
  dateStyle: "short", timeStyle: "short", timeZone: "Europe/Moscow",
});
export const number = (value) => numberFormat.format(value);

export function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

export function cell(row, text, className = "") {
  const node = element("td", className, text);
  row.append(node);
  return node;
}

export function button(label, action, className = "text-button") {
  const node = element("button", className, label);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}

export function notice(id, message = "") {
  const node = byId(id);
  node.textContent = message;
  node.hidden = !message;
}

export function tableState(prefix, message, loading = false) {
  const node = byId(`${prefix}-status`);
  node.textContent = message;
  node.hidden = !message;
  byId(`${prefix}-table-card`).setAttribute("aria-busy", String(loading));
}

export function numberClass(value) {
  return value < 0 ? "number-negative" : value === 0 ? "number-zero" : "number-positive";
}

export function dateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return dateFormat.format(date);
}

export function documentStatus(record) {
  if (record.is_deleted) return element("span", "badge reversal", "Обратная операция");
  if (record.is_cancelled) return element("span", "badge cancelled", "Отменена");
  return element("span", "badge posted", "Проведена");
}

export function documentTypeClass(type) {
  return type === "receipt" ? "receipt" : type === "transfer" ? "transfer" : "shipment";
}

export function fillSelect(select, records, placeholder, label) {
  const previous = select.value;
  select.replaceChildren(new Option(placeholder, ""));
  for (const record of records) select.add(new Option(label(record), String(record.id)));
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
}

export function confirmAction(title, description, confirmText) {
  const dialog = byId("confirm-dialog");
  byId("confirm-title").textContent = title;
  byId("confirm-description").textContent = description;
  byId("confirm-submit").textContent = confirmText;
  dialog.returnValue = "";
  return new Promise((resolve) => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true });
    dialog.showModal();
  });
}
