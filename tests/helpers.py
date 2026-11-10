# tests/helpers.py
import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import settings

# ⚠️ Ajusta los prefijos a como montas los routers en app.main
API = "/api/v1"
REGISTER_URL = f"{API}/users/register"
ME_URL = f"{API}/users/me"
LOGIN_URL = f"{API}/auth/login"

SPACES_URL = f"{API}/spaces/"  # con "/" final: el router define POST "/" y GET "/"
NEARBY_URL = f"{API}/spaces/nearby"
MY_SPACES_URL = f"{API}/spaces/my-spaces"

AVAIL_URL = f"{API}/availabilities/"
BOOKINGS_URL = f"{API}/bookings/"
BOOKINGS_ME_URL = f"{API}/bookings/me"
PAYMENTS_URL = f"{API}/payments/process"

EMAIL_DOMAIN = "pytest-qa.com"
DEFAULT_PASSWORD = "Str0ngPass!"

# Coordenadas base: Bogotá (Plaza de Bolívar)
BASE_LAT, BASE_LON = 4.5981, -74.0760


# --------------------------------------------------------------------------- #
# URLs con parámetros
# --------------------------------------------------------------------------- #
def space_url(space_id) -> str:
    return f"{API}/spaces/{space_id}"


def avail_space_url(space_id) -> str:
    return f"{API}/availabilities/space/{space_id}"


def avail_url(avail_id) -> str:
    return f"{API}/availabilities/{avail_id}"


def booking_url(booking_id) -> str:
    return f"{API}/bookings/{booking_id}"


def cancel_url(booking_id) -> str:
    return f"{API}/bookings/{booking_id}/cancel"


# --------------------------------------------------------------------------- #
# Usuarios y tokens
# --------------------------------------------------------------------------- #
def unique_email() -> str:
    """Email único con prefijo 'qa_' para que el cleanup pueda borrarlo."""
    return f"qa_{uuid.uuid4().hex[:12]}@{EMAIL_DOMAIN}"


def build_user_payload(**overrides) -> dict:
    payload = {
        "email": unique_email(),
        "full_name": "QA Tester",
        "password": DEFAULT_PASSWORD,
        "is_host": False,
    }
    payload.update(overrides)
    return payload


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_token(
    sub,
    *,
    secret: str | None = None,
    algorithm: str | None = None,
    expires_delta: timedelta | None = timedelta(minutes=15),
) -> str:
    """Genera JWTs arbitrarios (válidos, expirados, mal firmados, sin sub...)."""
    payload: dict = {}
    if sub is not None:
        payload["sub"] = str(sub)
    if expires_delta is not None:
        payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(
        payload,
        secret or settings.SECRET_KEY,
        algorithm=algorithm or settings.ALGORITHM,
    )


def make_alg_none_token(sub) -> str:
    """Token sin firma (alg=none): ataque clásico que debe ser rechazado."""

    def b64(d: dict) -> str:
        raw = json.dumps(d, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': str(sub)})}."


# --------------------------------------------------------------------------- #
# Espacios, reservas y pagos
# --------------------------------------------------------------------------- #
def build_space_payload(**overrides) -> dict:
    payload = {
        "title": "Parqueadero QA",
        "category": "PARKING",
        "address": "Calle 10 # 5-20",
        "neighborhood": "La Candelaria",
        "conditions": "Solo carros",
        "price_per_hour": 5000,
        "latitude": BASE_LAT,
        "longitude": BASE_LON,
        "photos": [],
    }
    payload.update(overrides)
    return payload


async def create_bookable_space(client, host_headers: dict, **space_overrides) -> dict:
    """Publica un espacio ($10.000/h por defecto) con disponibilidad desde ayer hasta +10 días."""
    payload = build_space_payload(price_per_hour=10000)
    payload.update(space_overrides)
    r = await client.post(SPACES_URL, json=payload, headers=host_headers)
    assert r.status_code == 201, r.text
    space = r.json()

    now = datetime.now(timezone.utc)
    a = await client.post(
        AVAIL_URL,
        json={
            "space_id": space["id"],
            "start_time": (now - timedelta(days=1)).isoformat(),
            "end_time": (now + timedelta(days=10)).isoformat(),
        },
        headers=host_headers,
    )
    assert a.status_code == 201, a.text
    return space


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def slot(*, offset: timedelta = timedelta(days=3), hours: int = 2) -> tuple[str, str]:
    """Rango de horas completas (minutos=0) como (inicio, fin) ISO. Por defecto: en 3 días, 2 h."""
    start = (datetime.now(timezone.utc) + offset).replace(
        minute=0, second=0, microsecond=0
    )
    return start.isoformat(), (start + timedelta(hours=hours)).isoformat()


def booking_payload(space_id, start: str, end: str) -> dict:
    return {"space_id": str(space_id), "start_time": start, "end_time": end}


def payment_payload(booking_id, simulated_status: str = "APPROVED") -> dict:
    return {
        "booking_id": str(booking_id),
        "payment_method": "CARD",
        "simulated_status": simulated_status,
    }
