import logging
from typing import Any

from facebook_business.adobjects.adsinsights import AdsInsights
from facebook_business.adobjects.campaign import Campaign
from facebook_business.api import FacebookAdsApi

logger = logging.getLogger(__name__)


class MetaMetricsCollector:
    def fetch_metrics(self, campanha_id: str, credentials_dict: dict[str, Any]) -> dict[str, Any]:
        try:
            token = (credentials_dict or {}).get("meta_bm_token")
            if not token:
                raise ValueError("Token Meta nao informado para coleta de metricas.")

            FacebookAdsApi.init(access_token=token)

            campaign = Campaign(campanha_id)
            insights = campaign.get_insights(
                fields=[
                    AdsInsights.Field.adset_name,
                    AdsInsights.Field.spend,
                    AdsInsights.Field.actions,
                ],
                params={
                    "date_preset": "last_3d",
                    "level": "adset",
                },
            )

            servicos: list[dict[str, Any]] = []
            total_spend = 0.0
            total_conversions = 0
            for insight in insights or []:
                nome_servico = str(insight.get("adset_name") or "").strip() or "Servico sem nome"
                spend = float(insight.get("spend", 0.0) or 0.0)
                actions = insight.get("actions", []) or []
                conversions = 0
                for action in actions:
                    if action.get("action_type") == "purchase":
                        conversions += int(float(action.get("value", 0) or 0))

                total_spend += spend
                total_conversions += conversions
                servicos.append(
                    {
                        "nome_servico": nome_servico,
                        "spend": spend,
                        "conversions": conversions,
                        "cpa": (spend / conversions if conversions > 0 else 0.0),
                    }
                )

            cpa_geral = (total_spend / total_conversions) if total_conversions > 0 else 0.0
            logger.info(
                "Metricas Meta (granular) coletadas. campanha_id=%s servicos=%s spend=%.2f conversions=%s",
                campanha_id,
                len(servicos),
                total_spend,
                total_conversions,
            )
            return {
                "spend": total_spend,
                "conversions": total_conversions,
                "cpa": cpa_geral,
                "servicos": servicos,
            }
        except Exception:
            logger.exception(
                "Falha ao coletar metricas granulares da Meta. campanha_id=%s",
                campanha_id,
            )
            return {"spend": 0.0, "conversions": 0, "cpa": 0.0, "servicos": []}
