FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias primero (mejor caché de capas de Docker).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Las nubes inyectan el puerto en $PORT; en local usamos 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
