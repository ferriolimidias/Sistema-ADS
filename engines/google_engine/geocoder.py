import logging

import httpx

logger = logging.getLogger(__name__)


async def obter_coordenadas(endereco: str, api_key: str) -> tuple[float, float] | None:
    if not endereco or not api_key:
        logger.warning("Geocoder sem endereco ou api_key; geocodificacao ignorada.")
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={
                    "address": endereco,
                    "key": api_key,
                },
            )
            response.raise_for_status()
            payload = response.json()

        if payload.get("status") == "OK" and payload.get("results"):
            location = payload["results"][0]["geometry"]["location"]
            lat = float(location["lat"])
            lng = float(location["lng"])
            return lat, lng

        logger.warning(
            "Geocoder nao retornou resultado valido. status=%s endereco=%s",
            payload.get("status"),
            endereco,
        )
        return None
    except Exception:
        logger.exception("Falha ao obter coordenadas no geocoder para endereco=%s", endereco)
        return None
