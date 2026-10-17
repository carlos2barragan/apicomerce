# 01 · Docker, explicado desde cero

Esta guía cubre **todo lo que hicimos para levantar el proyecto con Docker** y por
qué cada pieza existe. Léela en orden.

---

## 1. ¿Qué es Docker y por qué usarlo?

El problema que resuelve: *"en mi máquina funciona"*. Docker empaqueta tu app
**con todas sus dependencias** para que corra igual en cualquier lado.

Dos conceptos que confunden siempre:

| Concepto | Qué es | Analogía |
|---|---|---|
| **Imagen** | Plantilla inmutable (el "molde") | La receta de una torta |
| **Contenedor** | Una imagen en ejecución (el "molde lleno") | La torta horneada |

De una imagen puedes crear **muchos** contenedores. Si borras un contenedor, la
imagen sigue ahí. Los cambios dentro de un contenedor **se pierden** al borrarlo,
salvo que uses un **volumen** (ver sección 4).

---

## 2. El `Dockerfile` (receta de la API)

Está en la raíz del proyecto:

```dockerfile
FROM python:3.12-slim                 # 1. Imagen base: Python 3.12 liviana
WORKDIR /app                          # 2. Carpeta de trabajo dentro del contenedor
COPY requirements.txt .               # 3. Copia SOLO las dependencias primero
RUN pip install --no-cache-dir -r requirements.txt   # 4. Instala dependencias
COPY . .                              # 5. Copia el resto del código
EXPOSE 8000                           # 6. Documenta que usa el puerto 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]  # 7. Comando de arranque
```

Cosas clave que debes entender:

- **¿Por qué copiar `requirements.txt` antes que el código?** Por la **caché de
  capas**. Docker guarda cada instrucción como una capa. Si solo cambias tu código
  (no las dependencias), Docker reusa la capa del `pip install` y el build es
  rapidísimo. Si copiaras todo primero, cualquier cambio de código reinstalaría
  todo.
- **`--no-cache-dir`**: evita guardar basura de pip dentro de la imagen.
- **`--host 0.0.0.0`**: dentro del contenedor hay que escuchar en todas las
  interfaces, no en `127.0.0.1`, o no será accesible desde fuera.
- **`${PORT:-8000}`**: si una nube (Render, Railway) define `PORT`, lo usa; si no,
  8000. Truco para portabilidad.

### `.dockerignore`

Igual que `.gitignore` pero para el build. Evita enviar a la imagen cosas que no
necesita: `.venv/`, `__pycache__/`, `.git/`, `*.db` y **`.env`** (¡importante!
nunca metas secretos reales en la imagen). Por eso el `.env` que creaste para
correr local **no entra** al contenedor.

---

## 3. `docker-compose.yml` (orquestar varios servicios)

Un `Dockerfile` construye **una** imagen. Nuestro proyecto necesita **dos**
servicios: la API y la base de datos. Para eso sirve Compose: declarar varios
contenedores y cómo se relacionan.

```yaml
services:
  api:
    build: .                        # Construye desde el Dockerfile local
    restart: unless-stopped         # Si se cae, se reinicia solo (salvo que lo pares tú)
    ports:
      - "8000:8000"                 # host:contenedor -> http://localhost:8000
    environment:
      DATABASE_URL: postgresql+psycopg://postgres:postgres@db:5432/ecommerce
      JWT_SECRET: ${JWT_SECRET:-dev-secret-change-me-only-for-local}
    depends_on:
      db:
        condition: service_healthy  # Espera a que Postgres esté SANO antes de arrancar

  db:
    image: postgres:16              # Imagen oficial, no la construimos nosotros
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ecommerce
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data   # Los datos sobreviven al borrar el contenedor
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d ecommerce"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  pgdata:
```

Puntos que valen oro para una entrevista:

- **`ports: "8000:8000"`** es `host:contenedor`. Publica el puerto del contenedor
  en tu máquina.
- **La URL de la BD usa `db` como host**: `...@db:5432/...`. Dentro de la red de
  Compose, cada servicio es accesible por su **nombre de servicio** (`db`), no por
  `localhost`. Por eso `DATABASE_URL` apunta a `db` y no a `localhost`.
- **`${JWT_SECRET:-...}`**: Compose lee automáticamente el archivo `.env` de la
  carpeta y sustituye la variable. Así el contenedor usa tu secreto **largo** (64
  caracteres) del `.env`, y si no existe usa el valor por defecto. Esto arregló el
  warning `InsecureKeyLengthWarning` de PyJWT (el secreto original de 25 bytes es
  demasiado corto para HS256).
- **`postgres:16`** fija la versión. Nunca uses `latest` en producción.
- **`psycopg`**: es el driver que conecta SQLAlchemy con PostgreSQL (está en
  `requirements.txt`). SQLAlchemy necesita el prefijo `postgresql+psycopg://`.

---

## 4. Volúmenes: que los datos no mueran

Sin volumen, cuando haces `docker compose down` la base de datos **se borra**.
Con:

```yaml
volumes:
  - pgdata:/var/lib/postgresql/data
```

Postgres guarda sus datos en el volumen con nombre `pgdata`, que sobrevive. Por
eso decimos:

- `docker compose down` → para contenedores, **conserva** los datos.
- `docker compose down -v` → la `-v` borra también los volúmenes (**pierdes** la BD).

---

## 5. El bug que arreglamos (y por qué importa)

**Síntoma:** al levantar por primera vez, la API a veces moría al arrancar.

**Causa:** en `app/main.py` la app ejecuta `Base.metadata.create_all()` al
iniciar. Si Postgres aún no está listo, la conexión falla y el proceso muere.

**Solución:** usamos un **healthcheck** en el servicio `db` (`pg_isready`) y en
`api` pusimos:

```yaml
depends_on:
  db:
    condition: service_healthy
```

Así Compose arranca `api` **solo cuando la BD responde de verdad**, no apenas el
contenedor se crea. Es la diferencia entre `depends_on` a secas (solo espera que
el contenedor *exista*) y `condition: service_healthy` (espera que esté *sano*).

---

## 6. Flujo completo al hacer `docker compose up --build`

1. Compose construye la imagen `api` desde el `Dockerfile`.
2. Descarga la imagen `postgres:16`.
3. Crea una **red** interna (los servicios se ven por nombre).
4. Crea el **volumen** `pgdata`.
5. Levanta `db`, espera a que `pg_isready` dé OK.
6. Levanta `api`, ya con la BD lista.
7. La API crea las tablas y queda escuchando en `0.0.0.0:8000`.

Luego, para tener datos, corrimos el seed **dentro** del contenedor:

```powershell
docker compose exec api python seed.py
```

`exec` ejecuta un comando en un contenedor ya encendido (a diferencia de `run`,
que crea uno nuevo).

---

## 7. Comandos esenciales

```powershell
docker compose up --build -d      # construir y levantar en segundo plano (-d)
docker compose ps                 # ver estado de los contenedores
docker compose logs -f api        # ver logs en vivo de la API
docker compose exec api bash      # abrir una shell DENTRO del contenedor
docker compose exec api python seed.py   # correr el seed
docker compose restart api        # reiniciar solo la API
docker compose down               # parar (conserva datos)
docker compose down -v            # parar y borrar la base de datos
docker compose up -d --build api  # reconstruir solo la API tras cambiar código
```

> **Nota:** como el código se copia dentro de la imagen (`COPY . .`), cada cambio
> en el Python o en el frontend requiere **reconstruir** (`--build`). Para
> desarrollo fluido se monta el código como volumen y se corre `uvicorn --reload`
> (te lo dejo como ejercicio en `03-frontend.md`).
