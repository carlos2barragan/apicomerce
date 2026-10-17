# 04 · Chuleta de comandos

Todos los comandos que usamos, agrupados, listos para copiar.

---

## Docker / Docker Compose

```powershell
# Construir y levantar todo en segundo plano
docker compose up --build -d

# Reconstruir SOLO la API (tras cambiar código Python o el frontend)
docker compose up -d --build api

# Ver estado de los contenedores
docker compose ps

# Ver logs (en vivo con -f)
docker compose logs -f api
docker compose logs db --tail 50

# Ejecutar un comando DENTRO de un contenedor encendido
docker compose exec api python seed.py
docker compose exec api pytest -q
docker compose exec api bash          # (en Linux) abre shell
docker compose exec api sh            # alternativa si no hay bash

# Parar / reiniciar
docker compose restart api
docker compose stop
docker compose down                   # para y borra contenedores (conserva datos)
docker compose down -v                # + borra volúmenes (¡pierdes la BD!)

# Limpieza general
docker system prune -a                # borra imágenes/contenedores sin usar
docker volume ls
docker volume rm ecommerce-fastapi_pgdata
```

---

## Correr sin Docker (local con SQLite)

```powershell
# Crear entorno virtual (solo la primera vez)
py -3.12 -m venv .venv

# Activarlo
.\.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Crear .env desde el ejemplo
Copy-Item .env.example .env

# Poblar datos
python seed.py

# Arrancar con recarga automática
uvicorn app.main:app --reload
```

Abre: **http://127.0.0.1:8000/docs** (Swagger) y **http://127.0.0.1:8000/ui/** (panel).

---

## Tests

```powershell
# Con Docker
docker compose exec api pytest -q

# Local (venv activado)
pytest -q
pytest -v                    # detallado
pytest tests/test_orders.py  # solo un archivo
pytest -k "cache"            # solo tests que contengan "cache"
```

---

## Probar la API a mano (PowerShell)

```powershell
$base = "http://127.0.0.1:8000"

# Login (devuelve el JWT). Ojo: el campo es "username", no "email".
$login = Invoke-RestMethod -Uri "$base/auth/login" -Method Post `
  -ContentType "application/x-www-form-urlencoded" `
  -Body "username=admin@demo.com&password=admin1234"

$h = @{ Authorization = "Bearer " + $login.access_token }

# Usuario autenticado
Invoke-RestMethod -Uri "$base/auth/me" -Headers $h

# Listar productos
Invoke-RestMethod -Uri "$base/products/"

# Crear una orden
Invoke-RestMethod -Uri "$base/orders/" -Method Post -Headers $h `
  -ContentType "application/json" -Body '{"items":[{"product_id":2,"quantity":3}]}'

# Analítica (solo admin)
Invoke-RestMethod -Uri "$base/analytics/summary" -Headers $h
```

Con `curl` (si lo tienes):

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -d "username=admin@demo.com&password=admin1234"
```

---

## Git

```powershell
git status
git log --oneline -10
git diff
git add docker-compose.yml frontend docs
git commit -m "feat: panel web y guías de documentación"
```

---

## Útil del sistema

```powershell
# Ver quién ocupa un puerto (ej: 8000 o 5432)
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess

# Ver si algo responde
Invoke-WebRequest http://127.0.0.1:8000/health/ready -UseBasicParsing
```
