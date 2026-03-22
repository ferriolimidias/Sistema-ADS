import logging

from facebook_business.adobjects.adsinsights import AdsInsights
from facebook_business.adobjects.campaign import Campaign
from facebook_business.api import FacebookAdsApi

logger = logging.getLogger(__name__)


class MetaCollector:
    def obter_metricas_campanha(self, campanha_id: str, credentials_dict: dict):
        try:
            token = (credentials_dict or {}).get("meta_bm_token")
            if not token:
                raise ValueError("Token Meta nao informado para coleta de metricas.")

            FacebookAdsApi.init(access_token=token)

            campaign = Campaign(campanha_id)
            insights = campaign.get_insights(
                fields=[
                    AdsInsights.Field.spend,
                    AdsInsights.Field.actions,
                ],
                params={"date_preset": "last_3d"},
            )

            spend = 0.0
            conversions = 0

            if insights:
                insight = insights[0]
                spend = float(insight.get("spend", 0.0) or 0.0)
                actions = insight.get("actions", []) or []

                for action in actions:
                    if action.get("action_type") == "purchase":
                        conversions += int(float(action.get("value", 0) or 0))

            cpa = spend / conversions if conversions > 0 else 0.0

            logger.info(
                "Metricas Meta coletadas com sucesso. campanha_id=%s spend=%.2f conversions=%s cpa=%.2f",
                campanha_id,
                spend,
                conversions,
                cpa,
            )
            return {"spend": spend, "conversions": conversions, "cpa": cpa}
        except Exception:
            logger.exception(
                "Falha ao coletar metricas da Meta. campanha_id=%s",
                campanha_id,
            )
            return {"spend": 0.0, "conversions": 0, "cpa": 0.0}
