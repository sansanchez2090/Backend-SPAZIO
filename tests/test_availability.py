# tests/test_availability.py  (versión mínima)
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.helpers import AVAIL_URL, avail_space_url, avail_url

pytestmark = pytest.mark.asyncio

T0 = datetime(2030, 1, 1, 8, 0, tzinfo=timezone.utc)


def period(space_id, start_h: int, end_h: int) -> dict:
    return {
        "space_id": str(space_id),
        "start_time": (T0 + timedelta(hours=start_h)).isoformat(),
        "end_time": (T0 + timedelta(hours=end_h)).isoformat(),
    }


async def test_owner_creates_period(async_client, host, space):
    r = await async_client.post(
        AVAIL_URL, json=period(space["id"], 0, 4), headers=host["headers"]
    )
    assert r.status_code == 201
    assert r.json()["space_id"] == space["id"]
    uuid.UUID(r.json()["id"])


async def test_non_owner_gets_403(async_client, other_host, space):
    r = await async_client.post(
        AVAIL_URL, json=period(space["id"], 0, 4), headers=other_host["headers"]
    )
    assert r.status_code == 403


async def test_overlap_rejected_but_adjacent_accepted(async_client, host, space):
    await async_client.post(
        AVAIL_URL, json=period(space["id"], 0, 4), headers=host["headers"]
    )

    overlap = await async_client.post(
        AVAIL_URL, json=period(space["id"], 2, 6), headers=host["headers"]
    )
    adjacent = await async_client.post(
        AVAIL_URL, json=period(space["id"], 4, 8), headers=host["headers"]
    )

    assert overlap.status_code == 400
    assert adjacent.status_code == 201


@pytest.mark.parametrize("start_h,end_h", [(4, 4), (4, 2)])
async def test_end_not_after_start_returns_422(
    async_client, host, space, start_h, end_h
):
    r = await async_client.post(
        AVAIL_URL, json=period(space["id"], start_h, end_h), headers=host["headers"]
    )
    assert r.status_code == 422


async def test_list_is_public_and_ordered(async_client, host, space):
    for s, e in [(8, 12), (0, 4), (4, 8)]:  # insertados desordenados
        await async_client.post(
            AVAIL_URL, json=period(space["id"], s, e), headers=host["headers"]
        )

    r = await async_client.get(avail_space_url(space["id"]))  # sin token
    assert r.status_code == 200
    starts = [p["start_time"] for p in r.json()]
    assert len(starts) == 3 and starts == sorted(starts)


async def test_only_owner_can_delete(async_client, host, other_host, space):
    created = await async_client.post(
        AVAIL_URL, json=period(space["id"], 0, 4), headers=host["headers"]
    )
    url = avail_url(created.json()["id"])

    assert (
        await async_client.delete(url, headers=other_host["headers"])
    ).status_code == 403
    assert (await async_client.delete(url, headers=host["headers"])).status_code == 200
    assert (await async_client.get(avail_space_url(space["id"]))).json() == []
