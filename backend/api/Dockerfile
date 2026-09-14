# Dockerfile
# Etapa 1: Build
FROM python:3.11-slim AS builder

# Evitar que Python escriba archivos .pyc y forzar el modo unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Instalar dependencias del sistema necesarias para compilar paquetes (si es necesario)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# Etapa 2: Runtime
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Crear un usuario no root por seguridad
RUN adduser --disabled-password --gecos "" apiuser

WORKDIR /app

# Copiar wheels de la etapa de build e instalar
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache /wheels/* && rm -rf /wheels

# Copiar el código de la aplicación
COPY ./app ./app

# Asignar permisos al usuario no root
RUN chown -R apiuser:apiuser /app
USER apiuser

# Exponer el puerto
EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
