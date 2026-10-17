# 05 · Contrato de la API (OpenAPI / Swagger)

El "contrato" es el **acuerdo** entre el backend y quien lo consume (frontend,
app móvil, otro servicio, un agente). Define qué rutas existen, qué reciben, qué
devuelven y qué errores pueden dar.

En FastAPI el contrato **se genera solo** a partir del código (las anotaciones y
los schemas de Pydantic). Eso es OpenAPI, y Swagger UI es el visor.

---

## 1. Dónde ver el contrato

| Recurso | URL | Para qué |
|---|---|---|
| **Swagger UI** | http://127.0.0.1:8000/docs | Probar endpoints desde el navegador |
| **ReDoc** | http://127.0.0.1:8000/redoc | Documentación de lectura, más limpia |
| **OpenAPI JSON** | http://127.0.0.1:8000/openapi.json | El contrato máquina-legible |
| **Panel web** | http://127.0.0.1:8000/ui | La interfaz que hicimos |

El `openapi.json` es lo que consumen herramientas como **Postman** (import →
OpenAPI), generadores de SDK, o validadores de contrato.

### Cómo probar rutas protegidas en Swagger UI

1. `POST /auth/login` → **Try it out** → `username=admin@demo.com`,
   `password=admin1234` → Execute.
2. Copia el `access_token`.
3. Botón **Authorize** (arriba a la derecha) → pega el token → Authorize.
4. Ya puedes probar cualquier ruta protegida; Swagger añade el `Authorization`
   automáticamente.

---

## 2. Convenciones

- **Base URL (local):** `http://127.0.0.1:8000`
- **Formato:** JSON (`application/json`), excepto el login.
- **Auth:** header `Authorization: Bearer <token>`.
- **Formato de error estándar:**
  ```json
  { "detail": "Descripción del error" }
  ```
- **Códigos de estado usados:**

  | Código | Significado |
  |---|---|
  | 200 | OK |
  | 201 | Creado |
  | 204 | Sin contenido (borrado) |
  | 400 | Petición inválida (ej: stock insuficiente) |
  | 401 | No autenticado / token inválido |
  | 403 | Autenticado pero sin permiso (no admin) |
  | 404 | No encontrado |
  | 422 | Error de validación (Pydantic) |
  | 429 | Demasiadas peticiones (rate limit) |
  | 503 | Servicio no disponible (BD caída) |

---

## 3. Endpoints

### 3.1 `auth`

#### `POST /auth/register` — Registrar usuario
- **Auth:** no
- **Body (JSON):**
  ```json
  { "email": "jane@example.com", "full_name": "Jane Doe", "password": "supersecreto123" }
  ```
- **201** → `UserRead`
  ```json
  { "email": "jane@example.com", "full_name": "Jane Doe", "id": 2,
    "is_active": true, "is_admin": false, "created_at": "2026-10-15T00:00:00Z" }
  ```
- **400** si el email ya existe · **422** si el password tiene < 8 caracteres.

#### `POST /auth/login` — Obtener token
- **Auth:** no
- **Content-Type:** `application/x-www-form-urlencoded`
- **Body:** `username=<email>&password=<password>`
  > ⚠️ Ojo: el campo es `username` (no `email`). Lo exige `OAuth2PasswordRequestForm`.
- **200** → `{ "access_token": "eyJ...", "token_type": "bearer" }`
- **401** si las credenciales son incorrectas.

#### `GET /auth/me` — Usuario actual
- **Auth:** sí (Bearer)
- **200** → `UserRead` · **401** si el token falta o es inválido.

### 3.2 `products`

#### `GET /products/` — Listar
- **Auth:** no · **Query:** `skip` (≥0), `limit` (1–100, def. 20), `q` (busca por nombre)
- **200** → `ProductRead[]` (cacheado por `CACHE_TTL_SECONDS`)

#### `GET /products/{id}` — Detalle
- **200** → `ProductRead` · **404** si no existe o está inactivo.

#### `POST /products/` — Crear 🔒 admin
- **Body (JSON):**
  ```json
  { "name": "Monitor 27\"", "description": "IPS 1440p", "price": "420.00", "stock": 15 }
  ```
- **201** → `ProductRead` · **403** si no eres admin.

#### `PATCH /products/{id}` — Actualizar 🔒 admin
- **Body:** solo los campos a cambiar, ej `{ "price": "399.99", "stock": 25 }`
- **200** → `ProductRead` · **403** / **404**.

#### `DELETE /products/{id}` — Eliminar 🔒 admin
- **204** (borrado lógico: `is_active=false`) · **403** / **404**.

### 3.3 `orders`

#### `POST /orders/` — Crear orden
- **Auth:** sí
- **Body (JSON):**
  ```json
  { "items": [ { "product_id": 1, "quantity": 2 }, { "product_id": 3, "quantity": 1 } ] }
  ```
- **201** → `OrderRead` (descuenta stock, invalida caché, envía correo en background)
  ```json
  { "id": 1, "user_id": 1, "status": "pending", "total": "5150.00",
    "created_at": "...", "items": [ { "id": 1, "product_id": 1, "quantity": 2, "unit_price": "2500.00" } ] }
  ```
- **400** stock insuficiente · **404** producto inexistente · **401** sin token.

#### `GET /orders/` — Mis órdenes
- **Auth:** sí · **200** → `OrderRead[]`

#### `GET /orders/{id}` — Detalle
- **Auth:** sí · **200** → `OrderRead` · **404** si no es tuya.

### 3.4 `analytics`

#### `GET /analytics/summary` — Resumen de ventas 🔒 admin
- **200** →
  ```json
  { "total_orders": 3, "total_revenue": 5150.0,
    "top_products": [ { "name": "Laptop 14\"", "units_sold": 4 } ] }
  ```
- **403** si no eres admin.

### 3.5 `health`

| Método | Ruta | Descripción | Códigos |
|---|---|---|---|
| GET | `/` | Info de la app | 200 |
| GET | `/health/live` | Liveness | 200 |
| GET | `/health/ready` | Readiness (chequea BD) | 200 / 503 |
| GET | `/metrics` | Métricas Prometheus | 200 (text/plain) |

---

## 4. Schemas (modelos de datos)

| Schema | Campos | Se usa en |
|---|---|---|
| `UserCreate` | email, full_name, password | Body de register |
| `UserRead` | id, email, full_name, is_active, is_admin, created_at | Respuestas de user |
| `Token` | access_token, token_type | Respuesta de login |
| `ProductBase` | name, description, price, stock | Base de producto |
| `ProductCreate` | (ProductBase) | Body de crear producto |
| `ProductUpdate` | name?, description?, price?, stock?, is_active? | Body de PATCH |
| `ProductRead` | (ProductBase) + id, is_active, created_at | Respuestas de producto |
| `OrderItemCreate` | product_id, quantity | Item al crear orden |
| `OrderCreate` | items[] | Body de crear orden |
| `OrderItemRead` | id, product_id, quantity, unit_price | Item en respuesta |
| `OrderRead` | id, user_id, status, total, created_at, items[] | Respuesta de orden |
| `ErrorResponse` | detail | Cualquier error |

> Todos estos schemas aparecen con su forma exacta en
> http://127.0.0.1:8000/openapi.json dentro de `components.schemas`.

---

## 5. Ejemplo de uso con cURL / PowerShell

```powershell
$base = "http://127.0.0.1:8000"

# 1) Login
$login = Invoke-RestMethod -Uri "$base/auth/login" -Method Post `
  -ContentType "application/x-www-form-urlencoded" `
  -Body "username=admin@demo.com&password=admin1234"
$h = @{ Authorization = "Bearer " + $login.access_token }

# 2) Crear producto (admin)
Invoke-RestMethod -Uri "$base/products/" -Method Post -Headers $h `
  -ContentType "application/json" `
  -Body '{"name":"Webcam","description":"1080p","price":"60.00","stock":12}'

# 3) Crear orden (cualquier usuario)
Invoke-RestMethod -Uri "$base/orders/" -Method Post -Headers $h `
  -ContentType "application/json" -Body '{"items":[{"product_id":1,"quantity":1}]}'
```

---

## 6. Cómo lo enriquecimos (y por qué importa)

En el código añadimos a cada endpoint:

```python
@router.post(
    "/",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un producto (solo admin)",
    description="Requiere rol de administrador...",
    responses={403: {"model": ErrorResponse, "description": "Se requiere rol de administrador"}},
)
```

- **`summary` / `description`** → aparecen en Swagger; documentan el *por qué*.
- **`responses`** → documentan los errores posibles con su schema.
- **`json_schema_extra={"example": {...}}`** en los schemas → Swagger muestra un
  ejemplo listo para "Try it out".
- **`openapi_tags`** en `main.py` → agrupa y describe las secciones del Swagger.

**¿Por qué importa?** Un contrato claro = menos idas y vueltas con el frontend,
menos bugs de integración, y herramientas (Postman, generadores de SDK,
validadores) trabajan solas. Es una de las cosas que más se valoran en un
back-end serio.
