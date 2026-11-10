from pydantic import BaseModel


class GeocodeResult(BaseModel):
    address: str
    latitude: float
    longitude: float


class AddressSuggestion(BaseModel):
    display_name: str
    latitude: float
    longitude: float
