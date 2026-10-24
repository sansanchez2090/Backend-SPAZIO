FROM python:3.11-slim

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar Poetry
RUN pip install --no-cache-dir poetry

# Copiar primero los archivos de dependencias para aprovechar el caché de Docker
COPY pyproject.toml poetry.lock ./

# Configurar Poetry para que no cree entornos virtuales dentro del contenedor (instala globalmente en el contenedor)
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --ansi

# Copiar el resto del código del proyecto
COPY . .

# Exponer el puerto en el que corre FastAPI
EXPOSE 8000

# Comando para arrancar la aplicación
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]