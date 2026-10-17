/* =========================================================
   Ecommerce Panel - frontend vanilla (sin frameworks)
   Habla con la misma API FastAPI usando fetch.
   El token JWT se guarda en localStorage.
   ========================================================= */

const API = "";
const PAGE_SIZE = 20;

const NAV_LABELS = { resumen: "Resumen", products: "Productos", orders: "Órdenes", analytics: "Analítica", status: "Estado" };

// ---------- Estado en memoria ----------
let token = localStorage.getItem("token") || null;
let me = null;
let productsCache = [];
let allProducts = [];
let ordersCache = [];
let cart = [];
let productPage = { skip: 0, q: "" };

// ---------- Atajos del DOM ----------
const $ = (sel) => document.querySelector(sel);
const setText = (sel, v) => { const n = $(sel); if (n) n.textContent = v; };
function el(html) { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; }
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const ICON_OK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
const ICON_ERR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg>';

/* =========================================================
   CAPA HTTP
   ========================================================= */
function formatDetail(detail, status) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((e) => {
      const campo = (e.loc || []).filter((x) => x !== "body").join(".");
      return campo ? `${campo}: ${e.msg}` : e.msg;
    }).join(" · ");
  }
  return detail ? JSON.stringify(detail) : `Error ${status}`;
}

function errorMessage(status, detail) {
  if (status === 403) return "No tienes permisos para esta acción.";
  if (status >= 500) return "Algo falló en el servidor. Intenta de nuevo en unos segundos.";
  return formatDetail(detail, status);
}

async function api(path, opts = {}) {
  const headers = {};
  if (opts.auth && token) headers["Authorization"] = "Bearer " + token;

  let body;
  if (opts.json) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = new URLSearchParams(opts.form).toString();
  }

  let res;
  try {
    res = await fetch(API + path, { method: opts.method || "GET", headers, body });
  } catch {
    throw new Error("No hay conexión con el servidor.");
  }

  if (res.status === 401 && opts.auth) {
    logout();
    throw new Error("Sesión expirada. Vuelve a entrar.");
  }
  if (res.status === 204) return null;

  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(errorMessage(res.status, data && data.detail));
  return data;
}

/* =========================================================
   UI: toasts / loader / pendiente / secciones
   ========================================================= */
function toast(msg, type = "ok") {
  const region = $("#toast-region");
  const node = el(`
    <div class="toast ${type === "error" ? "error" : "ok"}" role="${type === "error" ? "alert" : "status"}">
      <span class="toast__icon" aria-hidden="true">${type === "error" ? ICON_ERR : ICON_OK}</span>
      <span class="toast__msg"></span>
      <button type="button" class="toast__close" aria-label="Cerrar notificación">✕</button>
    </div>`);
  node.querySelector(".toast__msg").textContent = msg;
  region.prepend(node);
  requestAnimationFrame(() => node.classList.add("is-in"));
  [...region.children].slice(3).forEach((n) => n.remove());

  let timer;
  const dismiss = () => {
    clearTimeout(timer);
    node.classList.add("is-out");
    node.addEventListener("transitionend", () => node.remove(), { once: true });
  };
  node.querySelector(".toast__close").addEventListener("click", dismiss);
  timer = setTimeout(dismiss, type === "error" ? 6000 : 4000);
  node.addEventListener("mouseenter", () => clearTimeout(timer));
  node.addEventListener("mouseleave", () => { timer = setTimeout(dismiss, 1500); });
}

let _loaderTimer;
function showLoader(on) {
  const node = $("#loader");
  clearTimeout(_loaderTimer);
  if (on) _loaderTimer = setTimeout(() => node.classList.remove("hidden"), 150);
  else node.classList.add("hidden");
}

function money(v) { return "$" + Number(v).toLocaleString("es-CO", { minimumFractionDigits: 2 }); }

async function withPending(btn, fn) {
  if (!btn) return fn();
  if (btn.dataset.loading === "true") return;
  btn.dataset.loading = "true";
  btn.setAttribute("aria-busy", "true");
  try { return await fn(); }
  finally { btn.dataset.loading = "false"; btn.removeAttribute("aria-busy"); }
}

function renderSectionError(container, err, retry) {
  const box = $(container);
  box.innerHTML = "";
  const node = el(`<div class="card error-state"><p class="error"></p><button type="button" class="btn">Reintentar</button></div>`);
  node.querySelector(".error").textContent = err.message;
  node.querySelector("button").addEventListener("click", retry);
  box.appendChild(node);
}

/* =========================================================
   SESIÓN
   ========================================================= */
function logout() {
  token = null; me = null; productsCache = []; allProducts = []; ordersCache = []; cart = [];
  localStorage.removeItem("token");
  $("#app-view").classList.add("hidden");
  $("#login-view").classList.remove("hidden");
}

async function afterLogin() {
  me = await api("/auth/me", { auth: true });
  $("#login-view").classList.add("hidden");
  $("#app-view").classList.remove("hidden");
  $("#user-info").textContent = me.email;
  document.querySelectorAll(".admin-only").forEach((n) => n.classList.toggle("hidden", !me.is_admin));

  await loadDashboardProducts();
  await loadProducts();
  await loadOrders();
  renderDashboard();
  if (me.is_admin) loadAnalytics();
  checkHealth();
}

/* =========================================================
   LOGIN / REGISTRO
   ========================================================= */
$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#login-btn");
  $("#login-error").classList.add("hidden");
  showLoader(true);
  try {
    const data = await withPending(btn, () =>
      api("/auth/login", { method: "POST", form: { username: $("#login-email").value, password: $("#login-password").value } }));
    token = data.access_token;
    localStorage.setItem("token", token);
    await afterLogin();
    toast("Bienvenido, " + me.email);
  } catch (err) {
    const box = $("#login-error");
    box.textContent = err.message;
    box.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    showLoader(false);
  }
});

$("#register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#register-btn");
  try {
    await withPending(btn, () =>
      api("/auth/register", { method: "POST", json: {
        email: $("#reg-email").value,
        full_name: $("#reg-name").value || null,
        password: $("#reg-password").value,
      } }));
    toast("Cuenta creada. Ya puedes entrar.");
    e.target.reset();
  } catch (err) {
    toast(err.message, "error");
  }
});

$("#logout-btn").addEventListener("click", logout);

/* =========================================================
   NAVEGACIÓN (sidebar + drawer móvil)
   ========================================================= */
const navTrigger = $("#nav-trigger");
const scrim = $("#scrim");
function openNav() { document.body.classList.add("nav-open"); navTrigger.setAttribute("aria-expanded", "true"); scrim.hidden = false; }
function closeNav() { document.body.classList.remove("nav-open"); navTrigger.setAttribute("aria-expanded", "false"); scrim.hidden = true; }
navTrigger.addEventListener("click", () => (document.body.classList.contains("nav-open") ? closeNav() : openNav()));
scrim.addEventListener("click", closeNav);

function activateTab(name, { updateUrl = true } = {}) {
  const btn = document.querySelector(`.nav-item[data-tab="${name}"]`);
  if (!btn || btn.classList.contains("hidden")) return;
  document.querySelectorAll(".nav-item").forEach((b) => { b.classList.remove("active"); b.removeAttribute("aria-current"); });
  btn.classList.add("active");
  btn.setAttribute("aria-current", "page");
  document.querySelectorAll(".view").forEach((p) => p.classList.add("hidden"));
  const panel = $("#tab-" + name);
  if (panel) panel.classList.remove("hidden");
  setText("#crumb-current", NAV_LABELS[name] || name);
  if (updateUrl) history.replaceState({}, "", "#" + name);
  closeNav();

  if (name === "resumen") renderDashboard();
  if (name === "orders") loadOrders();
  if (name === "analytics" && me && me.is_admin) loadAnalytics();
  if (name === "status") checkHealth();
}

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => activateTab(btn.dataset.tab));
});

/* =========================================================
   COMMAND PALETTE (Ctrl/Cmd + K)
   ========================================================= */
const palette = $("#palette");
const paletteInput = $("#palette-input");
const paletteList = $("#palette-list");
let paletteActive = 0;
let paletteItems = [];

function paletteCommands() {
  const cmds = [
    { label: "Ir a Resumen", group: "Navegar", kbd: "", run: () => activateTab("resumen") },
    { label: "Ir a Productos", group: "Navegar", run: () => activateTab("products") },
    { label: "Ir a Órdenes", group: "Navegar", run: () => activateTab("orders") },
    { label: "Ir a Analítica", group: "Navegar", admin: true, run: () => activateTab("analytics") },
    { label: "Ir a Estado", group: "Navegar", run: () => activateTab("status") },
    { label: "Refrescar datos", group: "Acciones", run: () => { loadDashboardProducts(); loadProducts(); loadOrders(); if (me && me.is_admin) loadAnalytics(); } },
    { label: "Cerrar sesión", group: "Acciones", run: () => logout() },
  ];
  return cmds.filter((c) => !c.admin || (me && me.is_admin));
}

function renderPalette(query = "") {
  const q = query.trim().toLowerCase();
  const cmds = paletteCommands();
  paletteItems = q ? cmds.filter((c) => c.label.toLowerCase().includes(q)) : cmds.slice(0, 6);
  paletteList.innerHTML = "";
  if (!paletteItems.length) {
    paletteList.appendChild(el(`<li class="palette__empty">Sin resultados para “${escapeHtml(query)}”.</li>`));
    paletteInput.removeAttribute("aria-activedescendant");
    return;
  }
  paletteActive = 0;
  let lastGroup = null;
  paletteItems.forEach((c, i) => {
    if (c.group !== lastGroup) {
      lastGroup = c.group;
      paletteList.appendChild(el(`<li class="palette__group" role="presentation">${c.group}</li>`));
    }
    const item = el(`
      <li role="none">
        <button type="button" class="palette__item" role="option" id="pal-opt-${i}" aria-selected="${i === 0}">
          <span>${escapeHtml(c.label)}</span>
          ${c.kbd ? `<kbd class="palette__kbd">${c.kbd}</kbd>` : ""}
        </button>
      </li>`);
    const option = item.querySelector(".palette__item");
    option.addEventListener("click", () => runPalette(i));
    option.addEventListener("mousemove", () => setPaletteActive(i));
    paletteList.appendChild(item);
  });
  setPaletteActive(0);
}

function setPaletteActive(i) {
  if (!paletteItems.length) return;
  paletteActive = (i + paletteItems.length) % paletteItems.length;
  paletteList.querySelectorAll(".palette__item").forEach((node, n) => node.setAttribute("aria-selected", n === paletteActive));
  const active = paletteList.querySelector(`#pal-opt-${paletteActive}`);
  if (active) {
    paletteInput.setAttribute("aria-activedescendant", active.id);
    active.scrollIntoView({ block: "nearest" });
  }
}

function runPalette(i) {
  const cmd = paletteItems[i];
  if (!cmd) return;
  palette.close();
  cmd.run();
}

function openPalette() {
  paletteInput.value = "";
  renderPalette("");
  palette.showModal();
  paletteInput.focus();
}
$("#search-trigger").addEventListener("click", openPalette);
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    if (palette.open) palette.close(); else openPalette();
  }
});
paletteInput.addEventListener("input", () => renderPalette(paletteInput.value));
paletteInput.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown") { e.preventDefault(); setPaletteActive(paletteActive + 1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); setPaletteActive(paletteActive - 1); }
  else if (e.key === "Enter") { e.preventDefault(); runPalette(paletteActive); }
});

/* =========================================================
   RESUMEN
   ========================================================= */
function renderDashboard() {
  const list = allProducts.length ? allProducts : productsCache;
  const active = list.filter((p) => p.is_active !== false);
  const units = active.reduce((s, p) => s + (Number(p.stock) || 0), 0);
  const inventory = active.reduce((s, p) => s + Number(p.price) * (Number(p.stock) || 0), 0);
  const orders = ordersCache || [];
  const spent = orders.reduce((s, o) => s + Number(o.total), 0);

  setText("#dash-products", active.length);
  setText("#dash-units", units);
  setText("#dash-inventory", money(inventory));
  setText("#dash-orders", orders.length);
  setText("#dash-spent", money(spent));
}

async function loadDashboardProducts() {
  try { allProducts = await api("/products/?limit=100"); }
  catch { allProducts = productsCache; }
}

/* =========================================================
   PRODUCTOS
   ========================================================= */
function skeletonCards(n = 6) {
  return Array.from({ length: n }, () => `<div class="skeleton"></div>`).join("");
}

async function loadProducts(q = productPage.q, skip = 0) {
  const box = $("#products-list");
  if (!productsCache.length) box.innerHTML = skeletonCards();
  box.setAttribute("aria-busy", "true");
  try {
    const params = new URLSearchParams({ limit: PAGE_SIZE, skip });
    if (q) params.set("q", q);
    const list = await api("/products/?" + params.toString());
    productsCache = list;
    productPage = { skip, q };
    renderProducts(list);
    renderPagination(list, skip);
    renderProductOptions(allProducts.length ? allProducts : list);
  } catch (err) {
    renderSectionError("#products-list", err, () => loadProducts(q, skip));
    setText("#products-count", "");
  } finally {
    box.removeAttribute("aria-busy");
  }
}

function renderPagination(list, skip) {
  const from = list.length ? skip + 1 : 0;
  const to = skip + list.length;
  setText("#products-count", list.length ? `Mostrando ${from}–${to}` : "Sin resultados");
  $("#products-prev").disabled = skip <= 0;
  $("#products-next").disabled = list.length < PAGE_SIZE;
}

function renderProducts(list) {
  const box = $("#products-list");
  box.innerHTML = "";
  if (!list.length) {
    box.appendChild(el(`
      <div class="card empty-state">
        <p class="muted">No hay productos que coincidan.</p>
        <button type="button" id="clear-search" class="btn">Limpiar búsqueda</button>
      </div>`));
    const clear = $("#clear-search");
    if (clear) clear.addEventListener("click", () => { $("#product-search").value = ""; loadProducts("", 0); });
    return;
  }
  for (const p of list) {
    const card = el(`
      <div class="card product-card">
        <strong>${escapeHtml(p.name)}</strong>
        <span class="desc">${escapeHtml(p.description || "")}</span>
        <span class="price">${money(p.price)}</span>
        <span class="stock">Stock: ${p.stock}</span>
        <div class="actions">
          <button class="btn edit-product admin-only" data-id="${p.id}">Editar</button>
          <button class="btn ghost delete-product admin-only" data-id="${p.id}">Eliminar</button>
        </div>
      </div>`);
    box.appendChild(card);
  }
  document.querySelectorAll(".edit-product").forEach((b) =>
    b.addEventListener("click", () => openEdit(Number(b.dataset.id))));
  document.querySelectorAll(".delete-product").forEach((b) =>
    b.addEventListener("click", () => deleteProduct(Number(b.dataset.id))));
  document.querySelectorAll("#products-list .admin-only").forEach((n) =>
    n.classList.toggle("hidden", !me || !me.is_admin));
}

const editDialog = $("#edit-dialog");

function openEdit(id) {
  const p = productsCache.find((x) => x.id === id) || allProducts.find((x) => x.id === id);
  if (!p) return;
  $("#edit-id").value = p.id;
  $("#edit-name").value = p.name;
  $("#edit-desc").value = p.description || "";
  $("#edit-price").value = p.price;
  $("#edit-stock").value = p.stock;
  editDialog.showModal();
}
$("#edit-cancel").addEventListener("click", () => editDialog.close());
$("#edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = Number($("#edit-id").value);
  try {
    await withPending($("#edit-save"), () =>
      api(`/products/${id}`, { method: "PATCH", auth: true, json: {
        name: $("#edit-name").value,
        description: $("#edit-desc").value || null,
        price: $("#edit-price").value,
        stock: Number($("#edit-stock").value),
      } }));
    editDialog.close();
    toast("Producto actualizado");
    await loadDashboardProducts();
    await loadProducts($("#product-search").value, productPage.skip);
    renderDashboard();
  } catch (err) {
    toast(err.message, "error");
  }
});

function confirmDialog(message) {
  return new Promise((resolve) => {
    const dlg = $("#confirm-dialog");
    $("#confirm-message").textContent = message;
    const ok = $("#confirm-ok");
    const cancel = $("#confirm-cancel");
    const finish = (value) => { dlg.close(); ok.onclick = null; cancel.onclick = null; dlg.onclose = null; resolve(value); };
    ok.onclick = () => finish(true);
    cancel.onclick = () => finish(false);
    dlg.onclose = () => finish(false);
    dlg.showModal();
    cancel.focus();
  });
}

async function deleteProduct(id) {
  const p = productsCache.find((x) => x.id === id) || allProducts.find((x) => x.id === id);
  const name = p ? `“${p.name}”` : "este producto";
  if (!(await confirmDialog(`¿Eliminar ${name}? Se hará un borrado lógico.`))) return;
  try {
    await api(`/products/${id}`, { method: "DELETE", auth: true });
    toast("Producto eliminado");
    await loadDashboardProducts();
    await loadProducts($("#product-search").value, productPage.skip);
    renderDashboard();
  } catch (err) {
    toast(err.message, "error");
  }
}

$("#product-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector('button[type="submit"]');
  try {
    await withPending(btn, () =>
      api("/products/", { method: "POST", auth: true, json: {
        name: $("#p-name").value,
        description: $("#p-desc").value || null,
        price: $("#p-price").value,
        stock: Number($("#p-stock").value),
      } }));
    e.target.reset();
    toast("Producto creado");
    await loadDashboardProducts();
    await loadProducts("", 0);
    renderDashboard();
  } catch (err) {
    toast(err.message, "error");
  }
});

$("#product-search").addEventListener("input", (e) => {
  clearTimeout(e.target._t);
  e.target._t = setTimeout(() => loadProducts(e.target.value, 0), 300);
});
$("#product-refresh").addEventListener("click", () => loadProducts($("#product-search").value, productPage.skip));
$("#products-prev").addEventListener("click", () => loadProducts(productPage.q, Math.max(0, productPage.skip - PAGE_SIZE)));
$("#products-next").addEventListener("click", () => loadProducts(productPage.q, productPage.skip + PAGE_SIZE));

/* =========================================================
   ÓRDENES
   ========================================================= */
function renderProductOptions(list) {
  const sel = $("#order-product");
  const avail = list.filter((p) => p.stock > 0);
  const prev = sel.value;
  if (!avail.length) {
    sel.innerHTML = `<option value="">Sin productos con stock disponible</option>`;
    sel.disabled = true;
    $("#order-add-item").disabled = true;
    return;
  }
  sel.disabled = false;
  $("#order-add-item").disabled = false;
  sel.innerHTML = avail
    .map((p) => `<option value="${p.id}">${escapeHtml(p.name)} — ${money(p.price)} (stock ${p.stock})</option>`)
    .join("");
  if (avail.some((p) => String(p.id) === prev)) sel.value = prev;
}

function stockOf(productId) {
  const p = allProducts.find((x) => x.id === productId) || productsCache.find((x) => x.id === productId);
  return p ? Number(p.stock) : 0;
}

$("#order-add-item").addEventListener("click", () => {
  const productId = Number($("#order-product").value);
  const quantity = Number($("#order-qty").value);
  if (!productId || quantity < 1) return;
  const stock = stockOf(productId);
  if (stock <= 0) { toast("Ese producto no tiene stock disponible.", "error"); return; }
  if (quantity > stock) { toast(`Solo hay ${stock} unidades disponibles.`, "error"); return; }
  const existing = cart.find((l) => l.product_id === productId);
  if (existing) {
    if (existing.quantity + quantity > stock) { toast(`Solo hay ${stock} unidades disponibles.`, "error"); return; }
    existing.quantity += quantity;
  } else {
    cart.push({ product_id: productId, quantity });
  }
  renderCart();
});

function renderCart() {
  const ul = $("#order-cart");
  ul.innerHTML = "";
  cart.forEach((line, i) => {
    const p = productsCache.find((x) => x.id === line.product_id) || allProducts.find((x) => x.id === line.product_id);
    ul.appendChild(el(`
      <li>
        <span>${escapeHtml(p ? p.name : "Producto " + line.product_id)} × ${line.quantity}</span>
        <button class="btn ghost" data-i="${i}" aria-label="Quitar del carrito">✕</button>
      </li>`));
  });
  ul.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => { cart.splice(Number(b.dataset.i), 1); renderCart(); }));
  $("#order-submit").disabled = cart.length === 0;
}

$("#order-submit").addEventListener("click", async () => {
  const btn = $("#order-submit");
  btn.disabled = true;
  try {
    const order = await api("/orders/", { method: "POST", auth: true, json: { items: cart } });
    cart = [];
    renderCart();
    toast(`Orden #${order.id} creada por ${money(order.total)}`);
    await loadDashboardProducts();
    await loadProducts(productPage.q, productPage.skip);
    await loadOrders();
    renderDashboard();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = cart.length === 0;
  }
});

async function loadOrders() {
  const box = $("#orders-list");
  if (!ordersCache.length) box.innerHTML = `<div class="skeleton" style="height:88px"></div><div class="skeleton" style="height:88px"></div>`;
  try {
    ordersCache = await api("/orders/", { auth: true });
    renderOrders(ordersCache);
    renderDashboard();
  } catch (err) {
    renderSectionError("#orders-list", err, loadOrders);
  }
}

function renderOrders(orders) {
  const box = $("#orders-list");
  box.innerHTML = "";
  if (!orders.length) {
    box.appendChild(el(`<div class="card empty-state"><p class="muted">Aún no tienes órdenes. Crea una arriba.</p></div>`));
    return;
  }
  for (const o of orders) {
    const items = o.items.map((i) => {
      const p = allProducts.find((x) => x.id === i.product_id) || productsCache.find((x) => x.id === i.product_id);
      return `${escapeHtml(p ? p.name : "Producto " + i.product_id)} × ${i.quantity}`;
    }).join(" · ");
    box.appendChild(el(`
      <div class="card order-card">
        <div class="row space-between">
          <strong>Orden #${o.id}</strong>
          <span class="status-pill">${escapeHtml(o.status)}</span>
        </div>
        <span class="price">${money(o.total)}</span>
        <div class="order-items">${items}</div>
        <div class="muted">${new Date(o.created_at).toLocaleString()}</div>
      </div>`));
  }
}
$("#orders-refresh").addEventListener("click", loadOrders);

/* =========================================================
   ANALÍTICA (admin)
   ========================================================= */
async function loadAnalytics() {
  try {
    const s = await api("/analytics/summary", { auth: true });
    setText("#kpi-orders", s.total_orders);
    setText("#kpi-revenue", money(s.total_revenue));
    const box = $("#top-products");
    box.innerHTML = "";
    if (!s.top_products.length) {
      box.appendChild(el(`<p class="muted">Sin ventas todavía.</p>`));
    } else {
      s.top_products.forEach((t) =>
        box.appendChild(el(`<div class="card row space-between"><span>${escapeHtml(t.name)}</span><strong>${t.units_sold} u.</strong></div>`)));
    }
  } catch (err) {
    renderSectionError("#top-products", err, loadAnalytics);
  }
}

/* =========================================================
   ESTADO / SALUD
   ========================================================= */
async function checkHealth() {
  const badge = $("#health-badge");
  try {
    const info = await api("/");
    setText("#st-version", info.version);
    await api("/health/live");
    setText("#st-live", "Disponible");
    try {
      await api("/health/ready");
      setText("#st-ready", "BD disponible");
      badge.textContent = "online";
      badge.className = "badge badge-ok";
    } catch {
      setText("#st-ready", "BD no disponible");
      badge.textContent = "degradado";
      badge.className = "badge badge-warn";
    }
  } catch {
    badge.textContent = "offline";
    badge.className = "badge badge-error";
  }
}

$("#metrics-refresh").addEventListener("click", async () => {
  const btn = $("#metrics-refresh");
  try {
    await withPending(btn, async () => {
      const res = await fetch(API + "/metrics");
      if (!res.ok) throw new Error("No se pudieron obtener las métricas.");
      $("#metrics-box").textContent = await res.text();
    });
  } catch (err) {
    toast(err.message, "error");
  }
});

/* =========================================================
   ARRANQUE
   ========================================================= */
(async function init() {
  if (token) {
    try {
      await afterLogin();
      const hash = location.hash.replace("#", "");
      if (hash) activateTab(hash, { updateUrl: false });
      return;
    } catch {
      // token inválido: cae al login
    }
  }
  $("#login-view").classList.remove("hidden");
})();
