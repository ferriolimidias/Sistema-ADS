import logging

from engines.meta_engine.metrics import MetaMetricsCollector

logger = logging.getLogger(__name__)


class MetaCollector:
    def obter_metricas_campanha(self, campanha_id: str, credentials_dict: dict):
        data = MetaMetricsCollector().fetch_metrics(
            campanha_id=campanha_id,
            credentials_dict=credentials_dict,
        )
        logger.info("MetaCollector delegou coleta granular. campanha_id=%s", campanha_id)
        return data
