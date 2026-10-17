# Ecommerce API (FastAPI)

API REST de ecommerce para practicar **backend profesional en Python** y construir
un proyecto de portafolio que pase el filtro de las vacantes junior.

## Stack

| Capa | Tecnología | Por qué |
|---|---|---|
| Framework | **FastAPI** | Estándar moderno para APIs en Python |
| Servidor | **Uvicorn** | Servidor ASGI |
| ORM | **SQLAlchemy 2.0** | Modelado de datos |
| Validación | **Pydantic v2** | Schemas de entrada/salida |
| BD | **SQLite** (dev) / **PostgreSQL** (prod) | Relacional, lo más pedido |
| Auth | **JWT + bcrypt** | Autenticación stateless |
| Tests | **pytest + httpx** | Calidad y confianza |
| Deploy | **Docker / docker-compose** | Reproducibilidad |

## Estructura

```
app/
├── main.py        Punto de entrada. Monta la app, los routers y el panel /ui.
├── config.py      Variables de entorno (patrón 12-factor).
├── database.py    Motor de BD + sesión + dependencia get_db.
├── security.py    Hash de contraseñas y tokens JWT.
├── deps.py        Dependencias reutilizables (usuario actual, admin).
├── models/        Tablas (SQLAlchemy).
├── schemas/       Validación de datos (Pydantic).
└── routers/       Endpoints agrupados por recurso.
frontend/          Panel web (HTML/CSS/JS) servido en /ui.
docs/              Guías explicativas del proyecto.
tests/             Pruebas automatizadas.
seed.py            Carga datos de ejemplo.
```

## Cómo ejecutarlo

```powershell
# 1. Crear entorno virtual (solo la primera vez)
py -3.12 -m venv .venv

# 2. Activar el entorno
.\.venv\Scripts\Activate.ps1

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. (Opcional) Crear .env a partir del ejemplo
Copy-Item .env.example .env

# 5. Cargar datos de prueba
python seed.py

# 6. Arrancar el servidor con recarga automática
uvicorn app.main:app --reload
```

Abre **http://127.0.0.1:8000/docs** → documentación interactiva (Swagger UI).
Ahí puedes probar todos los endpoints sin escribir código cliente.

### Con Docker (incluye PostgreSQL)

```powershell
docker compose up --build -d
docker compose exec api python seed.py   # datos de ejemplo
```

### Panel web (ver los datos)

Abre **http://127.0.0.1:8000/ui/** → panel con login, productos, órdenes,
analítica (admin) y estado del servicio. Se sirve desde la misma API
(carpeta `frontend/`), sin frameworks ni paso de build.

## Documentación

Guías paso a paso en [`docs/`](docs/README.md):

- [01 · Docker](docs/01-docker.md) — el `Dockerfile` y el `docker-compose` explicados.
- [02 · Backend](docs/02-backend.md) — arquitectura FastAPI, auth, caché, observabilidad.
- [03 · Frontend](docs/03-frontend.md) — cómo está hecho el panel web.
- [04 · Comandos](docs/04-comandos.md) — chuleta de comandos.

## Endpoints

### Autenticación
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/auth/register` | Registra un usuario |
| POST | `/auth/login` | Login (form-urlencoded), devuelve JWT |
| GET | `/auth/me` | Datos del usuario autenticado |

### Productos
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/products/` | Lista (paginado, búsqueda con `?q=`) |
| GET | `/products/{id}` | Detalle |
| POST | `/products/` | Crear (solo admin) |
| PATCH | `/products/{id}` | Actualizar (solo admin) |
| DELETE | `/products/{id}` | Borrado lógico (solo admin) |

### Órdenes
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/orders/` | Crea una orden (descuenta stock) |
| GET | `/orders/` | Órdenes del usuario autenticado |
| GET | `/orders/{id}` | Detalle de una orden propia |

## Tests

```powershell
pytest -v
```

### Salud, métricas y analítica
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health/live` | Liveness (¿el proceso vive?) |
| GET | `/health/ready` | Readiness (¿la BD responde?) |
| GET | `/metrics` | Métricas en formato Prometheus |
| GET | `/analytics/summary` | Resumen de ventas (solo admin) |

## Capacidades de producción

- **Caché**: las lecturas de `/products` se cachean (Redis si hay `REDIS_URL`,
  si no en memoria). Las escrituras invalidan la caché. TTL configurable con
  `CACHE_TTL_SECONDS`.
- **Rate limiting**: máximo de peticiones por IP por minuto
  (`RATE_LIMIT_PER_MINUTE`, por defecto 120). Devuelve `429` al pasarse.
- **Observabilidad**: logs **JSON** con `request_id` único por petición, headers
  `X-Request-ID` y `X-Process-Time-ms`, contadores e histograma de latencia en
  `/metrics`.
- **Health checks**: `/health/live` y `/health/ready` para orquestadores
  (Kubernetes, Render).
- **Tareas en background**: al crear una orden se encola el correo de
  confirmación con `BackgroundTasks` (no bloquea la respuesta).
- **Analítica**: `/analytics/summary` usa agregaciones SQL (`COUNT`, `SUM`,
  `GROUP BY`, `JOIN`). Es la base perfecta para exponer "tools" a un agente LLM.

## Usuario de ejemplo

- Email: `admin@demo.com`
- Password: `admin1234`

---

# Guía de aprendizaje (ruta backend junior)

Ruta basada en lo que exigen las vacantes en Bogotá y Latam.

## Fase 1 — Fundamentos (meses 1-3)
- **Python sólido**: funciones, clases, comprenhensions, manejo de errores, `typing`.
- **HTTP**: métodos, códigos de estado (200/201/400/401/403/404/500), headers.
- **SQL**: `SELECT`, `JOIN`, `GROUP BY`, índices, transacciones.
- **Git**: ramas, commits, pull requests.
- Practica: añade filtros y orden a `/products`.

## Fase 2 — Backend real (meses 3-6)
- **Docker**: `docker build`, `docker run`, `docker compose`.
- **CI/CD**: GitHub Actions que corra `pytest` en cada push.
- **Deploy**: sube la API a Railway, Render o Fly.io (capa gratis).
- Practica: despliega y comparte la URL pública en tu CV.

## Fase 3 — Nivel producción (meses 6-9)
- **Redis** para caché y rate limiting.
- **Colas** (Celery / RQ) para tareas en background (ej: enviar email de compra).
- **Observabilidad**: logs estructurados, `/metrics` con Prometheus.
- **Migraciones** con Alembic (en vez de `create_all`).
- Practica: añade caché a `GET /products`.

## Fase 4 — Agentes / MCP (meses 9-12)
La apuesta que te diferencia. Casi ningún junior sabe esto.
- **MCP (Model Context Protocol)**: estándar para conectar agentes con herramientas.
  - Arquitectura cliente-servidor sobre JSON-RPC (transporte stdio o HTTP).
  - Primitivas: `tools` (acciones), `resources` (datos), `prompts`.
- **Patrón orquestador + workers**: un agente líder delega a subagentes. En Python
  se modela con `asyncio`, `TaskGroup`, timeouts y presupuesto de tokens.
- Practica: crea un **MCP server** que exponga esta API como *tools* y un agente que
  responda: *"¿cuánto vendí este mes y qué producto reabastecer?"*.

## Recursos
- FastAPI: https://fastapi.tiangolo.com
- SQLAlchemy 2.0: https://docs.sqlalchemy.org
- MCP: https://modelcontextprotocol.io
- Docker: https://docs.docker.com/get-started

---

# Preguntas típicas de entrevista (backend)

Prepáralas con este proyecto como referencia.

1. **¿Diferencia entre autenticación y autorización?** Login = autenticación;
   que solo el admin cree productos = autorización.
2. **¿Por qué usar JWT y no sesiones?** Stateless, escala horizontal, ideal para APIs.
   Menciona el trade-off: no se puede invalidar un token antes de que expire (por eso
   se usan refresh tokens o blacklist en Redis).
3. **¿Qué hace bcrypt?** Hashing + salting + factor de costo. Nunca guardes passwords
   en texto plano ni con MD5/SHA1.
4. **¿Qué es un índice en BD?** Acelera lecturas a cambio de escrituras más lentas.
   Aquí indexamos `email` (búsqueda por login) y claves foráneas.
5. **¿SQL vs NoSQL?** SQL para datos relacionales con integridad (pedidos, usuarios);
   NoSQL para datos flexibles/volumen alto.
6. **¿Cómo evitas sobreventa de stock?** Descuento dentro de la transacción y valido
   `stock >= quantity`. En concurrencia alta se usa `SELECT ... FOR UPDATE`.
7. **¿Qué es idempotencia?** Operación repetible sin efecto adicional (ej: reintentar un
   pago). Se resuelve con claves de idempotencia.
8. **¿Cómo escalarías esta API?** Réplicas detrás de un load balancer, BD con réplicas
   de lectura, caché con Redis, colas para lo pesado, contenedores en Kubernetes.
9. **¿Qué es un soft delete y por qué usarlo?** Marcar `is_active=False` en vez de
   borrar: conserva historial y evita romper claves foráneas.
10. **Diseña un sistema de órdenes** (típico). Habla de: modelo de datos, transacción,
    estados (`pending`/`paid`/`shipped`), eventos (Kafka) y manejo de fallos.
