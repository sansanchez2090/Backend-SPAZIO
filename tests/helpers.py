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

EMAIL_DOMAIN = "pytest-qa.com"
DEFAULT_PASSWORD = "Str0ngPass!"


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


SPACES_URL = f"{API}/spaces/"  # con "/" final: el router define POST "/" y GET "/"


def space_url(space_id) -> str:
    return f"{API}/spaces/{space_id}"


NEARBY_URL = f"{API}/spaces/nearby"
MY_SPACES_URL = f"{API}/spaces/my-spaces"

# Coordenadas base: Bogotá (Plaza de Bolívar)
BASE_LAT, BASE_LON = 4.5981, -74.0760


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
