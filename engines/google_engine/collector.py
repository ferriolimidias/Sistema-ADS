import logging

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

logger = logging.getLogger(__name__)


class GoogleCollector:
    def obter_metricas_campanha(self, customer_id: str, campanha_id: str, credentials_dict: dict):
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        campanha_id_limpo = (campanha_id or "").strip()

        try:
            google_ads_config = dict(credentials_dict or {})
            use_client_customer_id = google_ads_config.pop("use_client_customer_id", None)
            if use_client_customer_id:
                google_ads_config["login_customer_id"] = str(use_client_customer_id).replace("-", "").strip()

            client = GoogleAdsClient.load_from_dict(google_ads_config)
            googleads_service = client.get_service("GoogleAdsService")

            query = (
                "SELECT metrics.cost_micros, metrics.conversions "
                f"FROM campaign WHERE campaign.id = {campanha_id_limpo} "
                "AND segments.date DURING LAST_3_DAYS"
            )
            response = googleads_service.search(customer_id=customer_id_limpo, query=query)

            spend = 0.0
            conversions = 0

            for row in response:
                spend = float(row.metrics.cost_micros or 0) / 1000000.0
                conversions = int(float(row.metrics.conversions or 0))
                break

            cpa = spend / conversions if conversions > 0 else 0.0

            logger.info(
                "Metricas Google coletadas com sucesso. customer_id=%s campanha_id=%s spend=%.2f conversions=%s cpa=%.2f",
                customer_id_limpo,
                campanha_id_limpo,
                spend,
                conversions,
                cpa,
            )
            return {"spend": spend, "conversions": conversions, "cpa": cpa}
        except GoogleAdsException:
            logger.exception(
                "Falha GoogleAdsException ao coletar metricas do Google Ads. customer_id=%s campanha_id=%s",
                customer_id_limpo,
                campanha_id_limpo,
            )
            return {"spend": 0.0, "conversions": 0, "cpa": 0.0}
        except Exception:
            logger.exception(
                "Falha inesperada ao coletar metricas do Google Ads. customer_id=%s campanha_id=%s",
                customer_id_limpo,
                campanha_id_limpo,
            )
            return {"spend": 0.0, "conversions": 0, "cpa": 0.0}
