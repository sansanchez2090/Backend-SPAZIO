import hashlib
from decimal import Decimal
from typing import Optional

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


def amount_to_cents(amount: Decimal) -> int:
    return int((Decimal(str(amount)) * 100).to_integral_value())


def build_reference(booking_id) -> str:
    return f"SPAZIO-{booking_id}"


def generate_integrity_signature(reference: str, amount_in_cents: int) -> str:
    if not settings.WOMPI_INTEGRITY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="El secreto de integridad de Wompi no está configurado en el servidor.",
        )
    raw = f"{reference}{amount_in_cents}{settings.WOMPI_CURRENCY}{settings.WOMPI_INTEGRITY_SECRET}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def fetch_transaction(transaction_id: str) -> dict:
    if not settings.WOMPI_PRIVATE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="La llave privada de Wompi no está configurada en el servidor.",
        )
    url = f"{settings.WOMPI_BASE_URL.rstrip('/')}/transactions/{transaction_id}"
    headers = {"Authorization": f"Bearer {settings.WOMPI_PRIVATE_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo contactar a la pasarela de pagos: {exc}",
        )

    if resp.status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La transacción indicada no existe en Wompi.",
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Respuesta inesperada de Wompi (HTTP {resp.status_code}).",
        )

    body = resp.json()
    return body.get("data", {})


class WompiTransaction:
    def __init__(self, data: dict):
        self.id: Optional[str] = data.get("id")
        self.status: str = data.get("status", "")
        self.reference: Optional[str] = data.get("reference")
        self.amount_in_cents: Optional[int] = data.get("amount_in_cents")
        self.currency: Optional[str] = data.get("currency")
        self.payment_method_type: Optional[str] = data.get("payment_method_type")

    @property
    def is_approved(self) -> bool:
        return self.status == "APPROVED"


async def get_transaction(transaction_id: str) -> WompiTransaction:
    return WompiTransaction(await fetch_transaction(transaction_id))
