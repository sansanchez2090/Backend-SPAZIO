from typing import List, Optional

import httpx
from fastapi import HTTPException, status

from app.schemas.geocoding import AddressSuggestion, GeocodeResult

BOGOTA_VIEWBOX = "-74.25,4.84,-73.99,4.45"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"

_HEADERS = {
    "User-Agent": "SPAZIO-Parking-MVP/1.0 (academic project)",
    "Accept-Language": "es",
}
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


async def geocode_address(query: str) -> GeocodeResult:
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "viewbox": BOGOTA_VIEWBOX,
        "bounded": 1,
        "countrycodes": "co",
        "addressdetails": 1,
    }
    data = await _get("/search", params)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró ninguna ubicación para la dirección indicada.",
        )
    item = data[0]
    return GeocodeResult(
        address=item.get("display_name", query),
        latitude=float(item["lat"]),
        longitude=float(item["lon"]),
    )


async def suggest_addresses(query: str, limit: int = 5) -> List[AddressSuggestion]:
    query = (query or "").strip()
    if len(query) < 3:
        return []

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": max(1, min(limit, 10)),
        "viewbox": BOGOTA_VIEWBOX,
        "bounded": 1,
        "countrycodes": "co",
        "addressdetails": 1,
    }
    data = await _get("/search", params)
    return [
        AddressSuggestion(
            display_name=item.get("display_name", ""),
            latitude=float(item["lat"]),
            longitude=float(item["lon"]),
        )
        for item in data
        if item.get("lat") and item.get("lon")
    ]


async def reverse_geocode(latitude: float, longitude: float) -> GeocodeResult:
    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 18,
    }
    item = await _get("/reverse", params)
    if not item or "lat" not in item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró una dirección para las coordenadas indicadas.",
        )
    return GeocodeResult(
        address=item.get("display_name", ""),
        latitude=float(item["lat"]),
        longitude=float(item["lon"]),
    )


async def _get(path: str, params: dict):
    try:
        async with httpx.AsyncClient(
            base_url=NOMINATIM_BASE, headers=_HEADERS, timeout=_TIMEOUT
        ) as client:
            resp = await client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al consultar el servicio de geocodificación: {exc}",
        )
