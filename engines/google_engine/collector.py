import logging

from engines.google_engine.metrics import GoogleMetricsCollector

logger = logging.getLogger(__name__)


class GoogleCollector:
    def obter_metricas_campanha(self, customer_id: str, campanha_id: str, credentials_dict: dict):
        data = GoogleMetricsCollector().fetch_metrics(
            customer_id=customer_id,
            campanha_id=campanha_id,
            credentials_dict=credentials_dict,
        )
        logger.info(
            "GoogleCollector delegou coleta granular. customer_id=%s campanha_id=%s",
            (customer_id or "").replace("-", "").strip(),
            (campanha_id or "").strip(),
        )
        return data
