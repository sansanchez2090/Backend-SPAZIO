# tests/test_spaces.py  (versión esencial)
import uuid

import pytest

from tests.helpers import (
    create_bookable_space,
    ME_URL,
    BASE_LAT,
    BASE_LON,
    MY_SPACES_URL,
    NEARBY_URL,
    SPACES_URL,
    build_space_payload,
    space_url,
)

pytestmark = pytest.mark.asyncio


def ids(response) -> set[str]:
    """IDs del listado (se compara por id: la BD puede tener más datos)."""
    return {s["id"] for s in response.json()}


class TestCreateSpace:
    async def test_host_creates_space(self, async_client, host):
        payload = build_space_payload(category="STORAGE", price_per_hour=7500)
        r = await async_client.post(SPACES_URL, json=payload, headers=host["headers"])

        assert r.status_code == 201
        body = r.json()
        uuid.UUID(body["id"])
        assert body["host_id"] == host["id"]
        assert body["category"] == "STORAGE"
        assert body["price_per_hour"] == 7500
        assert body["is_active"] is True
        # La geometría PostGIS se convierte de vuelta a lat/lon
        assert body["latitude"] == pytest.approx(BASE_LAT)
        assert body["longitude"] == pytest.approx(BASE_LON)

    async def test_first_space_activates_host_role(self, async_client, guest):
        first = await async_client.post(
            SPACES_URL, json=build_space_payload(), headers=guest["headers"]
        )
        assert first.status_code == 201
        assert first.json()["host_role_activated"] is True

        me = await async_client.get(ME_URL, headers=guest["headers"])
        assert me.json()["is_host"] is True

        second = await async_client.post(
            SPACES_URL, json=build_space_payload(), headers=guest["headers"]
        )
        assert second.status_code == 201
        assert second.json()["host_role_activated"] is False

    async def test_create_requires_authentication(self, async_client):
        r = await async_client.post(SPACES_URL, json=build_space_payload())
        assert r.status_code in (401, 403)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"price_per_hour": 0},
            {"price_per_hour": -100},
            {"latitude": 91},
            {"longitude": 181},
            {"category": "NO_EXISTE"},
            {"photos": ["a", "b", "c", "d"]},  # máximo 3
        ],
    )
    async def test_invalid_data_returns_422(self, async_client, host, overrides):
        r = await async_client.post(
            SPACES_URL, json=build_space_payload(**overrides), headers=host["headers"]
        )
        assert r.status_code == 422

    async def test_missing_required_field_returns_422(self, async_client, host):
        payload = build_space_payload()
        payload.pop("address")
        r = await async_client.post(SPACES_URL, json=payload, headers=host["headers"])
        assert r.status_code == 422


class TestReadSpaces:
    async def test_list_includes_active_space(self, async_client, space):
        r = await async_client.get(SPACES_URL)
        assert r.status_code == 200
        assert space["id"] in ids(r)

    async def test_list_excludes_inactive_space(self, async_client, host, space):
        await async_client.put(
            space_url(space["id"]), json={"is_active": False}, headers=host["headers"]
        )
        r = await async_client.get(SPACES_URL)
        assert space["id"] not in ids(r)

    async def test_get_detail(self, async_client, space):
        r = await async_client.get(space_url(space["id"]))
        assert r.status_code == 200
        assert r.json()["id"] == space["id"]
        assert r.json()["address"] == space["address"]

    async def test_get_detail_not_found(self, async_client):
        r = await async_client.get(space_url(uuid.uuid4()))
        assert r.status_code == 404

    async def test_get_detail_invalid_uuid_returns_422(self, async_client):
        r = await async_client.get(space_url("no-es-uuid"))
        assert r.status_code == 422

    async def test_my_spaces_returns_only_own(
        self, async_client, host, other_host, space
    ):
        theirs = await async_client.post(
            SPACES_URL, json=build_space_payload(), headers=other_host["headers"]
        )
        r = await async_client.get(MY_SPACES_URL, headers=host["headers"])

        assert r.status_code == 200
        assert space["id"] in ids(r)
        assert theirs.json()["id"] not in ids(r)
        assert all(s["host_id"] == host["id"] for s in r.json())

    async def test_my_spaces_forbidden_for_non_host(self, async_client, guest):
        r = await async_client.get(MY_SPACES_URL, headers=guest["headers"])
        assert r.status_code == 403


class TestNearby:
    async def test_result_includes_distance_schedule_and_price(
        self, async_client, bookable_space
    ):
        r = await async_client.get(
            NEARBY_URL,
            params={"latitude": BASE_LAT, "longitude": BASE_LON, "radius": 500},
        )
        assert r.status_code == 200
        item = {s["id"]: s for s in r.json()}[bookable_space["id"]]

        assert (
            item["distance_meters"] < 5
        )  # el espacio está en el mismo punto de búsqueda
        assert item["price_per_hour"] == 10000
        assert len(item["availabilities"]) == 1
        window = item["availabilities"][0]
        assert window["start_time"] < window["end_time"]

    async def test_does_not_find_space_outside_radius(
        self, async_client, bookable_space
    ):
        # +0.1° de latitud ≈ 11 km al norte; radio de 1 km
        r = await async_client.get(
            NEARBY_URL,
            params={"latitude": BASE_LAT + 0.1, "longitude": BASE_LON, "radius": 1000},
        )
        assert r.status_code == 200
        assert bookable_space["id"] not in ids(r)

    async def test_results_are_sorted_by_distance(
        self, async_client, host, bookable_space
    ):
        far = await create_bookable_space(
            async_client, host["headers"], latitude=BASE_LAT + 0.003  # ≈ 330 m al norte
        )
        r = await async_client.get(
            NEARBY_URL,
            params={"latitude": BASE_LAT, "longitude": BASE_LON, "radius": 1000},
        )
        mine = [s for s in r.json() if s["id"] in {bookable_space["id"], far["id"]}]

        assert [s["id"] for s in mine] == [bookable_space["id"], far["id"]]
        assert 250 < mine[1]["distance_meters"] < 450

    async def test_lists_only_available_spaces_of_requested_category(
        self, async_client, host, bookable_space, space
    ):
        storage = await create_bookable_space(
            async_client, host["headers"], category="STORAGE"
        )
        r = await async_client.get(
            NEARBY_URL,
            params={
                "latitude": BASE_LAT,
                "longitude": BASE_LON,
                "radius": 500,
                "category": "PARKING",
            },
        )
        found = ids(r)
        assert bookable_space["id"] in found
        assert space["id"] not in found  # sin periodos de disponibilidad
        assert storage["id"] not in found  # otra categoría

    @pytest.mark.parametrize(
        "params",
        [
            {"latitude": 95, "longitude": 0},
            {"latitude": 0, "longitude": 200},
            {"latitude": 0, "longitude": 0, "radius": 0},
            {"longitude": 0},  # falta latitude
        ],
    )
    async def test_invalid_query_returns_422(self, async_client, params):
        r = await async_client.get(NEARBY_URL, params=params)
        assert r.status_code == 422


class TestUpdateSpace:
    async def test_owner_updates_and_changes_persist(self, async_client, host, space):
        r = await async_client.put(
            space_url(space["id"]),
            json={"title": "Nuevo título", "price_per_hour": 9000},
            headers=host["headers"],
        )
        assert r.status_code == 200
        assert r.json()["title"] == "Nuevo título"
        assert r.json()["address"] == space["address"]  # campos no enviados intactos

        persisted = (await async_client.get(space_url(space["id"]))).json()
        assert persisted["price_per_hour"] == 9000

    async def test_owner_updates_location(self, async_client, host, space):
        r = await async_client.put(
            space_url(space["id"]),
            json={"latitude": 4.7110, "longitude": -74.0721},
            headers=host["headers"],
        )
        assert r.status_code == 200
        assert r.json()["latitude"] == pytest.approx(4.7110)
        assert r.json()["longitude"] == pytest.approx(-74.0721)

    async def test_other_host_cannot_update(self, async_client, other_host, space):
        r = await async_client.put(
            space_url(space["id"]),
            json={"title": "Hackeado"},
            headers=other_host["headers"],
        )
        assert r.status_code == 403
        assert (await async_client.get(space_url(space["id"]))).json()[
            "title"
        ] == space["title"]

    async def test_update_not_found(self, async_client, host):
        r = await async_client.put(
            space_url(uuid.uuid4()), json={"title": "x"}, headers=host["headers"]
        )
        assert r.status_code == 404

    async def test_update_requires_authentication(self, async_client, space):
        r = await async_client.put(space_url(space["id"]), json={"title": "x"})
        assert r.status_code in (401, 403)

    async def test_invalid_update_returns_422(self, async_client, host, space):
        r = await async_client.put(
            space_url(space["id"]), json={"price_per_hour": -5}, headers=host["headers"]
        )
        assert r.status_code == 422


class TestDeleteSpace:
    async def test_owner_deletes_space(self, async_client, host, space):
        r = await async_client.delete(space_url(space["id"]), headers=host["headers"])
        assert r.status_code == 204
        assert (await async_client.get(space_url(space["id"]))).status_code == 404

    async def test_other_host_cannot_delete(self, async_client, other_host, space):
        r = await async_client.delete(
            space_url(space["id"]), headers=other_host["headers"]
        )
        assert r.status_code == 403
        assert (await async_client.get(space_url(space["id"]))).status_code == 200

    async def test_delete_not_found(self, async_client, host):
        r = await async_client.delete(space_url(uuid.uuid4()), headers=host["headers"])
        assert r.status_code == 404

    async def test_delete_requires_authentication(self, async_client, space):
        r = await async_client.delete(space_url(space["id"]))
        assert r.status_code in (401, 403)
