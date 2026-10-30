"use strict";
const $ = (id) => document.getElementById(id);
const state = { page: 1, limit: 10, totalPages: 1, editing: null, search: "", request: null };
const currency = (value) => new Intl.NumberFormat("en-US", {style:"currency",currency:"USD"}).format(value);
let searchTimer;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options, headers: { ...(options.body ? {"Content-Type":"application/json"} : {}), ...(options.headers || {}) }
  });
  if (response.status === 204) return null;
  const json = await response.json().catch(() => null);
  if (!response.ok) throw new Error(json?.error?.message || `Request failed (${response.status})`);
  return json;
}
function notice(message = "", error = false) {
  $("notice").textContent = message;
  $("notice").className = error ? "error" : "ok";
}
function cell(value) { const td = document.createElement("td"); td.textContent = String(value); return td; }
function action(text, callback) {
  const button = document.createElement("button");
  button.type = "button"; button.textContent = text; button.addEventListener("click", callback); return button;
}
async function load() {
  if (state.request) state.request.abort();
  const controller = new AbortController(); state.request = controller;
  const q = new URLSearchParams({page: state.page, limit: state.limit, search: state.search});
  try {
    const payload = await api(`/api/items?${q}`, {signal: controller.signal});
    const {data, meta} = payload;
    state.totalPages = Math.max(1, meta.pages);
    $("items").replaceChildren();
    for (const item of data) {
      const tr = document.createElement("tr");
      for (const value of [item.sku,item.name,item.category,item.quantity,currency(item.price)]) tr.append(cell(value));
      const actions = document.createElement("td");
      actions.append(action("Edit", () => startEdit(item)), " ", action("Delete", () => remove(item)));
      tr.append(actions); $("items").append(tr);
    }
    if (!data.length) {
      const tr = document.createElement("tr"), td = cell("No products found. Add your first item.");
      td.colSpan = 6; tr.append(td); $("items").append(tr);
    }
    $("total").textContent = meta.total; $("visible").textContent = data.length;
    $("page-number").textContent = meta.page; $("pagination").textContent = `Page ${meta.page} of ${state.totalPages}`;
    $("prev").disabled = state.page === 1; $("next").disabled = state.page >= state.totalPages;
    notice();
  } catch(e) { if(e.name !== "AbortError") notice(e.message, true); }
  finally { if(state.request === controller) state.request = null; }
}
function resetForm() {
  $("product-form").reset(); state.editing = null; $("form-title").textContent = "Add item";
  $("save").textContent = "Save item"; $("cancel").hidden = true;
}
function startEdit(item) {
  state.editing = item.id;
  for (const key of ["sku","name","category","quantity","price"]) $("product-form").elements.namedItem(key).value = item[key];
  $("form-title").textContent = `Edit ${item.sku}`; $("save").textContent = "Update item"; $("cancel").hidden = false;
}
async function remove(item) {
  if (!confirm(`Delete ${item.name} (${item.sku})?`)) return;
  try {
    await api(`/api/items/${item.id}`, {method:"DELETE"});
    if ($("items").rows.length === 1 && state.page > 1) state.page--;
    await load(); notice("Item deleted.");
    if (state.editing === item.id) resetForm();
  } catch(e) { notice(e.message, true); }
}
$("product-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const body = Object.fromEntries(new FormData(form));
  body.quantity = Number(body.quantity); body.price = Number(body.price);
  const isEdit = state.editing !== null;
  $("save").disabled = true;
  try {
    await api(isEdit ? `/api/items/${state.editing}` : "/api/items",
      {method: isEdit ? "PATCH" : "POST", body: JSON.stringify(body)});
    resetForm(); state.page = 1; await load(); notice(isEdit ? "Item updated." : "Item created.");
  } catch(e) { notice(e.message, true); }
  finally { $("save").disabled = false; }
});
$("cancel").addEventListener("click", resetForm);
$("search").addEventListener("input", (event) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {state.search = event.target.value.trim(); state.page = 1; load();}, 250);
});
$("prev").addEventListener("click", () => {if(state.page>1) {state.page--;load();}});
$("next").addEventListener("click", () => {if(state.page<state.totalPages) {state.page++;load();}});
load();
