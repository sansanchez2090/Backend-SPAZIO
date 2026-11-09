# tests/test_spaces.py
import pytest
import time

# Generamos correos únicos para evitar conflictos de duplicados en la base de datos
HOST_EMAIL = f"host_space_{int(time.time())}@spazio.com"
CLIENT_EMAIL = f"client_space_{int(time.time())}@spazio.com"
TEST_PASSWORD = "PasswordSeguro123"

# Variables globales para compartir IDs entre pruebas consecutivas
created_space_id = None


@pytest.mark.asyncio
async def test_register_and_login_host(async_client):
    """Registra y autentica un usuario anfitrión (is_host=True)."""
    # 1. Registrar anfitrión
    reg_response = await async_client.post(
        "/api/v1/users/register",
        json={
            "full_name": "Test Host User",
            "email": HOST_EMAIL,
            "password": TEST_PASSWORD,
            "is_host": True,
        },
    )
    assert reg_response.status_code in [200, 201]

    # 2. Iniciar sesión para obtener el token
    login_response = await async_client.post(
        "/api/v1/auth/login", json={"email": HOST_EMAIL, "password": TEST_PASSWORD}
    )
    assert login_response.status_code == 200
    data = login_response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_create_space_as_host(async_client):
    """Prueba la creación exitosa de un espacio geolocalizado por un anfitrión."""
    global created_space_id

    # Obtenemos el token de login del anfitrión
    login_response = await async_client.post(
        "/api/v1/auth/login", json={"email": HOST_EMAIL, "password": TEST_PASSWORD}
    )
    token = login_response.json()["access_token"]

    # Publicamos un espacio en Bogotá (ej: Parque de la 93 aprox)
    response = await async_client.post(
        "/api/v1/spaces/",
        json={
            "title": "Parqueadero Seguro Norte",
            "category": "PARKING",
            "address": "Calle 93 # 15-20",
            "neighborhood": "Chicó",
            "description": "Espacio cubierto con vigilancia 24/7",
            "conditions": "No vehículos pesados",
            "price_per_hour": 8500.0,
            "latitude": 4.6768,
            "longitude": -74.0482,
            "photos": ["https://supabase.co/storage/photo1.jpg"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Parqueadero Seguro Norte"
    assert "id" in data

    # Guardamos el ID para las siguientes pruebas de update/delete
    created_space_id = data["id"]


@pytest.mark.asyncio
async def test_search_spaces_nearby(async_client):
    """Prueba la búsqueda geoespacial utilizando PostGIS ST_DWithin en un radio de 1 km."""
    # Buscamos cerca de la misma coordenada (Lat: 4.6768, Lon: -74.0482)
    response = await async_client.get(
        "/api/v1/spaces/nearby",
        params={
            "latitude": 4.6768,
            "longitude": -74.0482,
            "radius": 1000.0,  # 1 kilómetro
        },
    )

    assert response.status_code == 200
    spaces = response.json()
    assert isinstance(spaces, list)
    assert len(spaces) > 0
    # Verificamos que nuestro espacio recién creado aparezca en los resultados
    assert any(space["id"] == created_space_id for space in spaces)


@pytest.mark.asyncio
async def test_update_space(async_client):
    """Prueba la actualización de los datos de un espacio por su propietario."""
    global created_space_id
    if not created_space_id:
        pytest.skip("No hay ID de espacio disponible debido a fallos previos.")

    login_response = await async_client.post(
        "/api/v1/auth/login", json={"email": HOST_EMAIL, "password": TEST_PASSWORD}
    )
    token = login_response.json()["access_token"]

    response = await async_client.put(
        f"/api/v1/spaces/{created_space_id}",
        json={
            "title": "Parqueadero Seguro Norte - Actualizado",
            "price_per_hour": 9500.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_space(async_client):
    """Prueba la eliminación de un espacio por el anfitrión propietario."""
    global created_space_id

    login_response = await async_client.post(
        "/api/v1/auth/login", json={"email": HOST_EMAIL, "password": TEST_PASSWORD}
    )
    token = login_response.json()["access_token"]

    response = await async_client.delete(
        f"/api/v1/spaces/{created_space_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204
