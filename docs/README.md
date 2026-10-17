# Documentación del proyecto

Guías escritas paso a paso para entender **cómo está hecho** este backend y su
panel web, pensadas para estudiar (no solo copiar).

| Doc | De qué trata |
|---|---|
| [01-docker.md](01-docker.md) | Qué es Docker, el `Dockerfile` y el `docker-compose` línea por línea, y el bug que arreglamos al arrancar. |
| [02-backend.md](02-backend.md) | Arquitectura de la API FastAPI: config, base de datos, modelos, auth JWT, caché, rate limiting, observabilidad y analítica. |
| [03-frontend.md](03-frontend.md) | Cómo construí el panel web (HTML/CSS/JS sin frameworks) y cómo se conecta a la API. |
| [04-comandos.md](04-comandos.md) | Chuleta de comandos (Docker, Python, pytest, git, curl). |

## Orden de lectura recomendado

1. **01-docker.md** → para entender cómo se levanta todo.
2. **02-backend.md** → el corazón del proyecto.
3. **03-frontend.md** → cómo se visualizan los datos.
4. **04-comandos.md** → para tener a mano mientras practicas.

## Mapa rápido del repositorio

```
ecommerce-fastapi/
├── app/                  # El backend (FastAPI)
│   ├── main.py           # Arranca la app, monta routers + el panel /ui
│   ├── config.py         # Variables de entorno (12-factor)
│   ├── database.py       # Motor SQLAlchemy y sesión
│   ├── models/           # Tablas (User, Product, Order, OrderItem)
│   ├── schemas/          # Validación de entrada/salida (Pydantic)
│   ├── routers/          # Endpoints por recurso
│   ├── cache.py          # Caché (Redis o memoria)
│   ├── deps.py           # Dependencias (usuario actual / admin)
│   ├── security.py       # bcrypt + JWT
│   ├── middleware.py     # request-id y rate limiting
│   ├── metrics.py        # Métricas Prometheus
│   └── notifications.py  # "Envío" de correo (background task)
├── frontend/             # El panel web (HTML/CSS/JS)
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── tests/                # Pruebas con pytest
├── seed.py               # Datos de ejemplo
├── Dockerfile            # Receta de la imagen de la API
├── docker-compose.yml    # API + PostgreSQL
└── requirements.txt      # Dependencias
```
