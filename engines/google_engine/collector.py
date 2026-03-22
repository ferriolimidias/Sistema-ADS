import logging

logger = logging.getLogger(__name__)


class GoogleCollector:
    def obter_metricas_campanha(self, campanha_id: str, credentials_dict: dict):
        logger.info(
            "Mock GoogleCollector consultando metricas da campanha. campanha_id=%s credenciais=%s",
            campanha_id,
            list((credentials_dict or {}).keys()),
        )
        return {"spend": 120.00, "conversions": 0, "cpa": 0.0}
