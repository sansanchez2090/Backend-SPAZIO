# 🅿️ SPAZIO - Backend API (MVP Parqueaderos Bogotá)

Backend oficial de **SPAZIO**, una plataforma colaborativa para la economía compartida de espacios físicos. Este MVP está optimizado para operar en la ciudad de **Bogotá** enfocado estrictamente en la categoría de **Parqueaderos** (según especificaciones del PMP y SRS).

---

## 🛠️ Stack Tecnológico

- **Framework:** FastAPI (Python 3.11+)
- **Gestor de Dependencias:** Poetry (v2.0+)
- **Base de Datos:** PostgreSQL con extensión PostGIS (Alojado en **Supabase**)
- **ORM:** SQLAlchemy (Asyncio) + Alembic
- **Geolocalización:** OpenStreetMap / Nominatim API + PostGIS (`ST_DWithin`)
- **Pasarela de Pagos:** Wompi (Entorno Sandbox / Simulación)
- **Contenedorización:** Docker

---

## 📂 Estructura del Proyecto

```text
spazio_backend/
├── database/                # Scripts SQL y esquemas de base de datos
│   └── schema.sql           # Script principal para Supabase
├── app/
│   ├── api/                 # Endpoints y rutas de la API (v1)
│   ├── core/                # Configuración global, DB async y seguridad (JWT)
│   ├── models/              # Modelos ORM (SQLAlchemy)
│   ├── schemas/             # Esquemas de validación (Pydantic)
│   ├── services/            # Lógica de negocio (Geo, Pagos, Reservas)
│   └── main.py              # Punto de entrada de FastAPI
├── tests/                   # Pruebas automatizadas (Pytest)
├── .env.example             # Plantilla de variables de entorno
├── Dockerfile               # Configuración para contenedores Docker
├── pyproject.toml           # Dependencias del proyecto (Poetry)
└── README.md
```

# ⚙️ Guía de Instalación y Configuración (Local)

Sigue estos pasos para levantar el entorno de desarrollo en tu máquina.

---

## Paso 0: Instalar Poetry

Si aún no tienes Poetry instalado en tu sistema, debes instalarlo utilizando el instalador oficial recomendado. Sigue las instrucciones detalladas en la documentación oficial:

- 🔗 [Guía de Instalación Oficial de Poetry](https://python-poetry.org/docs/#installation)

---

## Paso 1: Configurar Variables de Entorno

Crea una copia del archivo de ejemplo `.env.example` y nómbralo `.env`:

```bash
cp .env.example .env
```

Completa las variables requeridas en tu archivo `.env` (como tu `DATABASE_URL` asíncrona de Supabase y las llaves de prueba).

---

## Paso 2: Configuración de la Base de Datos en Supabase

Cada integrante del equipo debe usar su propio proyecto de Supabase:

1. Crea un proyecto gratuito en Supabase.
2. Ve al **SQL Editor** en tu panel de Supabase.
3. Copia el contenido del archivo ubicado en `database/schema.sql` de este repositorio, pégalo en el editor y ejecútalo (**Run**).
4. ⚠️ **Nota importante:** No actives _Row Level Security_ (RLS) en las tablas de Supabase para este proyecto, ya que la seguridad y validación de roles se gestiona directamente desde el backend en FastAPI.

---

## Paso 3: Instalación de Dependencias y Activación

Este proyecto utiliza Poetry para la gestión limpia de dependencias.

1. Instala las dependencias ejecutando en la raíz del proyecto:
   ```bash
   poetry install
   ```
2. Activa el entorno virtual (compatible con versiones de Poetry 2.0+):
   - **En PowerShell (Windows):**
     ```powershell
     Invoke-Expression (poetry env activate)
     ```
   - **En Bash (Linux / macOS / Git Bash):**
     ```bash
     eval $(poetry env activate)
     ```

---

## Paso 4: Ejecución del Servidor de Desarrollo

Una vez activo el entorno virtual, corre la aplicación con Uvicorn:

```bash
poetry run uvicorn app.main:app --reload
```

La API estará corriendo en `http://127.0.0.1:8000`. Puedes ver la documentación interactiva (Swagger UI) en `http://127.0.0.1:8000/docs`.

---

## 🐳 Ejecución mediante Docker

Si prefieres levantar el proyecto utilizando contenedores, puedes usar el `Dockerfile` incluido:

1. **Construye la imagen de Docker:**
   ```bash
   docker build -t spazio-backend .
   ```
2. **Ejecuta el contenedor pasando tu archivo `.env`:**
   ```bash
   docker run --rm -d -p 8000:8000 --env-file .env --name spazio-app spazio-backend
   ```

El servicio estará disponible en `http://localhost:8000`.

---

## 🧪 Ejecución de Pruebas Automatizadas

Para correr las pruebas unitarias y de integración configuradas con Pytest:

```bash
poetry run pytest
```
