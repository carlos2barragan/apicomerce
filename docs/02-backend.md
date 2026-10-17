# 02 · El backend, por dentro

Guía de la API FastAPI: cómo se organiza, cómo fluye una petición y qué hace cada
pieza del código.

---

## 1. El viaje de una petición

Cuando el navegador hace `GET /products/`, ocurre esto, en orden:

```
Navegador
   │  GET /products/
   ▼
[Middleware] RequestContextMiddleware  → genera un request_id, mide el tiempo
   │
   ▼
[Middleware] RateLimitMiddleware       → ¿esta IP pasó el límite? si no, 429
   │
   ▼
[Router] products.list_products()
   │
   ├─► [Caché] ¿está en caché? → devuelve sin tocar la BD
   │
   └─► [Dependencia] get_db() → abre una sesión SQLAlchemy
             │
             ▼
         [BD] SELECT ... FROM products
             │
             ▼
   [Pydantic] valida/convierte a JSON (ProductRead)
   │
   ▼
Respuesta JSON  +  headers X-Request-ID, X-Process-Time-ms
```

Entender este orden es entender FastAPI. Los **middlewares** envuelven todo; los
**routers** agrupan endpoints; las **dependencias** (`Depends`) inyectan cosas
(sesión de BD, usuario actual); **Pydantic** valida.

---

## 2. Configuración: patrón 12-factor (`config.py`)

Nada de secretos hardcodeados. Todo se lee de variables de entorno con valores
por defecto:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", ...)
    DATABASE_URL: str = "sqlite:///./ecommerce.db"
    JWT_SECRET: str = "dev-secret-change-me..."
    CACHE_TTL_SECONDS: int = 60
    RATE_LIMIT_PER_MINUTE: int = 120
    ...

settings = Settings()   # singleton: se importa desde cualquier módulo
```

**12-factor** = la configuración vive en el entorno, no en el código. Así la
misma imagen corre en dev (SQLite) y prod (PostgreSQL) sin recompilar.

---

## 3. Base de datos (`database.py` + `models/`)

`database.py` crea el **engine** (el "motor" de conexión) y una **fábrica de
sesiones**:

```python
engine = create_engine(database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db          # FastAPI inyecta esta sesión en el endpoint
    finally:
        db.close()        # y la cierra SIEMPRE, aunque haya error
```

- **`yield` en una dependencia**: el código antes del `yield` corre antes del
  endpoint; el `finally` corre después. Patrón para abrir/cerrar recursos.
- Fíjate que convierte `postgresql://` en `postgresql+psycopg://` porque
  SQLAlchemy 2.0 necesita el driver explícito.

Los **modelos** (`models/`) son las tablas. Ejemplo (`product.py`):

```python
class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True)
    price: Mapped[Decimal]
    stock: Mapped[int]
    is_active: Mapped[bool] = mapped_column(default=True)  # soft delete
```

- **`index=True`** en `email` y `name` acelera las búsquedas (login, buscar
  producto). Un índice acelera lecturas pero cuesta algo en escrituras.
- **`is_active`** implementa **soft delete**: "borrar" un producto es ponerlo en
  `False`, para no romper el histórico de órdenes.

---

## 4. Schemas: validación con Pydantic (`schemas/`)

Los modelos dicen cómo está **guardado**; los schemas, cómo se **entra y sale**.
Por eso `ProductCreate` (entrada) no tiene `id` y `ProductRead` (salida) sí:

```python
class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    price: Decimal = Field(gt=0)          # el precio debe ser > 0
    stock: int = Field(ge=0, default=0)   # stock >= 0

class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)  # leer desde el objeto SQLAlchemy
    id: int
    is_active: bool
    created_at: datetime
```

Si mandas `price: -5`, Pydantic devuelve **422** automáticamente, con el detalle
del error. Nunca tienes que validar eso a mano.

---

## 5. Autenticación: JWT + bcrypt

Tres piezas:

1. **`security.py`** — hashea passwords con `bcrypt` y firma/verifica tokens JWT
   con `PyJWT`.
2. **`routers/auth.py`** — `register`, `login`, `me`.
3. **`deps.py`** — dependencias que exigen estar logueado (`get_current_user`) o
   ser admin (`get_current_admin`).

### Flujo de login

```
POST /auth/login  (form-urlencoded: username=email, password=...)
   → verifica bcrypt del password
   → create_access_token(subject=user_id)
   → devuelve { "access_token": "eyJ...", "token_type": "bearer" }
```

El token JWT **no se guarda en la BD**: es *stateless*. Lleva firmado
`{sub: id, exp: ...}`. En cada petición protegida el cliente manda:

```
Authorization: Bearer eyJ...
```

`get_current_user` decodifica el token, saca el `id` y carga el usuario. Si el
token está vencido o mal firmado → **401**.

> **¿Por qué bcrypt y no SHA256?** bcrypt aplica *salting* y un factor de costo
> (es lento a propósito), lo que hace inviable un ataque de fuerza bruta. Nunca
> guardes contraseñas en texto plano ni con MD5/SHA1.

> **Trade-off del JWT:** no puedes invalidar un token antes de que expire. La
> solución profesional son *refresh tokens* o una *blacklist* en Redis.

---

## 6. Caché (`cache.py`)

Patrón **degradación elegante**: intenta usar Redis; si no hay `REDIS_URL` o el
servidor no responde, cae a una caché **en memoria**. Nunca dejes que una
dependencia externa tumbe tu app.

En `products.list_products()`:

```python
cached = cache.get(cache_key)
if cached is not None:
    return cached                      # rápido, sin tocar la BD
...
cache.set(cache_key, result, ttl=settings.CACHE_TTL_SECONDS)
```

### 🐛 El bug que arreglamos

**Síntoma:** creabas una orden, el stock bajaba en la BD... pero `GET /products/`
seguía mostrando el stock viejo durante hasta 60 segundos.

**Causa:** al crear la orden, `orders.create_order()` descontaba stock pero **no
invalidaba la caché** de productos. La caché seguía sirviendo el listado antiguo.

**Solución:** centralizamos el prefijo de la caché en `cache.py`:

```python
PRODUCTS_CACHE_PREFIX = "products:"
```

y en `orders.create_order()` añadimos:

```python
# El stock cambió: invalidamos la caché de productos.
cache.delete_prefix(PRODUCTS_CACHE_PREFIX)
```

**Lección:** cada vez que **escribes** datos, invalida las cachés que dependan de
esos datos. Si no, sirves información obsoleta (*stale data*).

---

## 7. Rate limiting (`middleware.py`)

`RateLimitMiddleware` cuenta peticiones por IP por minuto usando `cache.incr`.
Si superas `RATE_LIMIT_PER_MINUTE` (120), responde **429 Too Many Requests**.

Esto protege contra abuso y es una respuesta típica que verás en entrevistas
("¿cómo evitas que te tiren la API?").

---

## 8. Observabilidad

Dos middlewares / utilidades:

- **Logs JSON** (`logging_config.py`): cada petición se registra como una línea
  JSON con `request_id`, método, ruta, status y duración. Los logs JSON son
  procesables por máquinas (Elastic, Loki).
- **`RequestContextMiddleware`**: genera un `request_id` único y lo devuelve en
  el header `X-Request-ID`, más `X-Process-Time-ms`. Así puedes correlacionar un
  error del usuario con la línea exacta del log.
- **`/metrics`** (`metrics.py`): expone contadores e histogramas en formato
  **Prometheus**, listo para Grafana.

Regla de oro: **lo que no se mide no se puede mejorar.**

---

## 9. Tareas en background (`notifications.py`)

Al crear una orden, el envío del correo de confirmación se encola con
`BackgroundTasks`:

```python
background_tasks.add_task(send_order_confirmation, current_user.email, order.id, ...)
```

La respuesta al cliente sale de inmediato; el correo se "envía" después. En un
sistema real esto iría a una cola (Celery/RQ) para sobrevivir si el proceso se
cae. Aquí basta para entender el concepto.

---

## 10. Analítica: agregaciones SQL (`routers/analytics.py`)

`GET /analytics/summary` (solo admin) usa funciones de agregación:

```python
total_orders = select(func.count(Order.id))
total_revenue = select(func.coalesce(func.sum(Order.total), 0))
top = (select(Product.name, func.sum(OrderItem.quantity))
       .join(OrderItem, ...)
       .group_by(Product.id, Product.name)
       .order_by(func.sum(OrderItem.quantity).desc())
       .limit(5))
```

`COUNT`, `SUM`, `JOIN`, `GROUP BY`. Son exactamente las operaciones que caen en
una entrevista y, además, la base perfecta para exponer "tools" a un agente LLM.

---

## 11. Tests (`tests/`)

Corren con `pytest` y usan el `TestClient` de FastAPI (que usa `httpx`). Cubren
auth, productos, órdenes, caché y analítica:

```powershell
docker compose exec api pytest -q
# 12 passed
```

Escribir tests es lo que separa un proyecto de portafolio de un ejercicio de
curso. Prioriza probar la **lógica de negocio** (crear orden descuenta stock) más
que los detalles obvios.
