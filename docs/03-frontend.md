# 03 · El panel web (frontend), cómo lo hice

El objetivo: **ver los datos de la API** (productos, órdenes, analítica) sin
escribir SQL ni usar Postman.

---

## 1. Decisión clave: ¿framework o HTML/JS puro?

Opciones y por qué elegí:

| Opción | Pros | Contras |
|---|---|---|
| **HTML + CSS + JS puro** ✅ | Cero toolchain, funciona ya, fácil de leer | A mano a medida que crece |
| React + Vite | Estándar de la industria | Necesita Node, build, más config |
| Vue/Svelte | Menos ceremoniosos | Otra dependencia |

Como el objetivo era **aprender y ver datos rápido**, fui con **vanilla JS
servido directamente por FastAPI**. No hay `npm`, ni build, ni `node_modules`.
Todo el panel son **3 archivos**.

> Cuando el proyecto crezca, migrar a React es un buen siguiente paso (sección 8).

---

## 2. Cómo se sirve: `StaticFiles` en FastAPI

FastAPI no solo da JSON; también puede servir archivos estáticos. Lo montamos en
`app/main.py`:

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# ...después de incluir los routers...

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/ui", StaticFiles(directory=_frontend_dir, html=True), name="ui")
```

Qué significa:

- **`app.mount("/ui", ...)`**: todo lo que esté bajo `/ui` se sirve como archivos.
  Abres `http://127.0.0.1:8000/ui/` y ves el panel.
- **`html=True`**: si pides una carpeta, busca automáticamente `index.html`.
- **El `if _frontend_dir.is_dir()`**: evita que la app falle si la carpeta no
  existe (por ejemplo en un entorno que solo corre tests).
- **Por qué `/ui` y no `/`**: porque `/` ya responde con un JSON de health. Montar
  en la raíz chocaría con las rutas de la API y con esa. `/ui` los mantiene
  separados: **API en un lado, panel en otro, mismo servidor** (sin problemas de
  CORS porque es el mismo origen).

---

## 3. Estructura del frontend

```
frontend/
├── index.html   → estructura (HTML) de las vistas
├── styles.css   → todo el diseño
└── app.js       → la lógica: hablar con la API y pintar datos
```

`index.html` tiene dos vistas que se muestran/ocultan con CSS:

- **`#login-view`**: tarjeta de login (y un `details` para registrarse).
- **`#app-view`**: barra superior + pestañas (Productos, Órdenes, Analítica,
  Estado) + el contenido.

### El patrón `hidden`

En vez de crear/destruir elementos, todo está en el DOM y alternamos la clase
`hidden` (que aplica `display: none`). Es la técnica más simple para una SPA:

```css
.hidden { display: none !important; }
```

---

## 4. Cómo habla con la API: la función `api()`

Todo pasa por un único helper en `app.js`:

```javascript
async function api(path, opts = {}) {
  const headers = {};
  if (opts.auth && token) headers["Authorization"] = "Bearer " + token;

  let body;
  if (opts.json) {                      // body JSON (registro, producto, orden)
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {               // login: x-www-form-urlencoded
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = new URLSearchParams(opts.form).toString();
  }

  const res = await fetch(path, { method: opts.method || "GET", headers, body });

  if (res.status === 401) { logout(); throw new Error("Sesión expirada"); }
  if (res.status === 204) return null;                // No Content
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.detail || `Error ${res.status}`);
  return data;
}
```

Detalles que importan:

- **Rutas relativas** (`"/products/"`): como el panel se sirve del mismo servidor
  que la API, no hace falta escribir `http://localhost:8000`. Cero problemas de
  CORS.
- **El login usa `form-urlencoded`, no JSON.** Esto confunde a muchos: FastAPI
  usa `OAuth2PasswordRequestForm`, que espera el campo `username` (¡no `email`!)
  y `password`. Por eso en el código el body es
  `{ username: email, password }`.
- **El token va en el header `Authorization: Bearer ...`** en cada petición
  protegida.
- **Un solo lugar maneja errores.** Si el backend responde 401 (token vencido),
  cerramos sesión automáticamente.

---

## 5. La sesión: JWT en `localStorage`

```javascript
let token = localStorage.getItem("token") || null;

// al hacer login:
token = data.access_token;
localStorage.setItem("token", token);
await afterLogin();

// al arrancar la página, si hay token, intenta recuperar el usuario:
if (token) { try { await afterLogin(); } catch { /* token inválido → login */ } }
```

- **`localStorage`** guarda el token para que sobreviva al recargar la página.
- Al arrancar, si hay token, pedimos `/auth/me`. Si el token está vencido, la
  función `api()` recibe 401, cierra sesión y muestra el login.

> **Seguridad (importante para entrevistas):** guardar el JWT en `localStorage` es
> cómodo pero vulnerable a XSS (si un script malicioso corre, roba el token). En
> producción seria se usan cookies **HttpOnly + Secure + SameSite**. Lo dejamos en
> `localStorage` porque es didáctico y este es un proyecto de práctica.

---

## 6. Pintar los datos

### Productos

```javascript
async function loadProducts(q = "") {
  const url = "/products/?limit=100" + (q ? `&q=${encodeURIComponent(q)}` : "");
  productsCache = await api(url);
  renderProducts(productsCache);
  renderProductOptions(productsCache);   // pobla el <select> de órdenes
}
```

`renderProducts` recorre la lista y crea tarjetas. Fíjate en algo crítico para
seguridad: **escapamos el HTML** antes de insertarlo.

```javascript
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
```

Sin esto, un producto llamado `<img src=x onerror=alert(1)>` ejecutaría código
(**XSS**). Nunca insertes datos del usuario directo con `innerHTML`.

### Órdenes

El usuario arma un "carrito" en memoria (`cart = []`), se ve en la lista, y al
confirmar se manda el cuerpo que espera la API:

```javascript
await api("/orders/", { method: "POST", auth: true, json: { items: cart } });
```

donde `cart` es `[{ product_id: 2, quantity: 3 }, ...]`. Tras crearla,
**recargamos productos** porque el stock cambió (y gracias al arreglo del backend,
la caché ya se invalida).

### Analítica (solo admin)

Pinta unos KPI y el top de productos. Los elementos `.admin-only` se ocultan si el
usuario no es admin:

```javascript
document.querySelectorAll(".admin-only")
  .forEach((n) => n.classList.toggle("hidden", !me.is_admin));
```

> Ojo: esto es solo **cosmético**. La verdadera seguridad está en el **backend**
> (`get_current_admin`). Esconder un botón no impide que alguien llame a la API
> directo. Siempre autoriza en el servidor.

---

## 7. Estado / salud

La pestaña "Estado" llama a `/health/live`, `/health/ready` y muestra `/metrics`
crudo. También la barra superior tiene un badge que indica si la API está
`online`, `degradado` u `offline`.

---

## 8. Cómo mejorarlo (ejercicios)

1. **Modo desarrollo con recarga en caliente**: en `docker-compose.yml`, monta el
   código como volumen y corre `uvicorn --reload`:

   ```yaml
   api:
     volumes:
       - .:/app
     command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

   Así no reconstruyes la imagen en cada cambio.

2. **Migrar a React + Vite**: cuando el panel crezca. Misma API, mismo JWT.
3. **Paginación** en la tabla de productos (`skip`/`limit` ya existen en la API).
4. **Editar productos** (ya existe `PATCH /products/{id}`): añade un formulario.
5. **Gráfico de ventas**: usa `/analytics/summary` con una librería como Chart.js.
6. **Tests de front** con Playwright o Cypress.
