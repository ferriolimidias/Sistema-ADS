import logging
from typing import Any

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

logger = logging.getLogger(__name__)


class GoogleMetricsCollector:
    @staticmethod
    def _build_google_client(credentials_dict: dict[str, Any]) -> GoogleAdsClient:
        google_ads_config = dict(credentials_dict or {})
        use_client_customer_id = google_ads_config.pop("use_client_customer_id", None)
        if use_client_customer_id:
            google_ads_config["login_customer_id"] = str(use_client_customer_id).replace("-", "").strip()
        return GoogleAdsClient.load_from_dict(google_ads_config)

    def fetch_metrics(self, customer_id: str, campanha_id: str, credentials_dict: dict[str, Any]) -> dict[str, Any]:
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        campanha_id_limpo = (campanha_id or "").strip()

        try:
            client = self._build_google_client(credentials_dict)
            googleads_service = client.get_service("GoogleAdsService")

            query = (
                "SELECT ad_group.name, metrics.cost_micros, metrics.conversions "
                "FROM ad_group "
                f"WHERE campaign.id = {campanha_id_limpo} "
                "AND segments.date DURING LAST_3_DAYS"
            )
            response = googleads_service.search(customer_id=customer_id_limpo, query=query)

            servicos: list[dict[str, Any]] = []
            total_spend = 0.0
            total_conversions = 0
            for row in response:
                nome_servico = str(getattr(row.ad_group, "name", "") or "").strip() or "Servico sem nome"
                spend = float(getattr(row.metrics, "cost_micros", 0) or 0) / 1_000_000.0
                conversoes = int(float(getattr(row.metrics, "conversions", 0) or 0))
                total_spend += spend
                total_conversions += conversoes
                servicos.append(
                    {
                        "nome_servico": nome_servico,
                        "spend": spend,
                        "conversions": conversoes,
                        "cpa": (spend / conversoes if conversoes > 0 else 0.0),
                    }
                )

            cpa_geral = (total_spend / total_conversions) if total_conversions > 0 else 0.0
            logger.info(
                "Metricas Google (granular) coletadas. customer_id=%s campanha_id=%s servicos=%s spend=%.2f conversions=%s",
                customer_id_limpo,
                campanha_id_limpo,
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
        except GoogleAdsException:
            logger.exception(
                "Falha GoogleAdsException no fetch_metrics do Google Ads. customer_id=%s campanha_id=%s",
                customer_id_limpo,
                campanha_id_limpo,
            )
            return {"spend": 0.0, "conversions": 0, "cpa": 0.0, "servicos": []}

    def fetch_search_terms(
        self,
        customer_id: str,
        campaign_id: str,
        periodo_dias: int = 7,
        credentials_dict: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        campaign_id_limpo = (campaign_id or "").strip()
        dias = max(1, int(periodo_dias or 7))
        try:
            if not credentials_dict:
                raise ValueError("credentials_dict e obrigatorio para consultar search_term_view.")
            client = self._build_google_client(credentials_dict)
            googleads_service = client.get_service("GoogleAdsService")

            query = (
                "SELECT "
                "search_term_view.search_term, "
                "segments.date, "
                "ad_group.id, "
                "ad_group.name, "
                "metrics.clicks, "
                "metrics.impressions, "
                "metrics.cost_micros, "
                "metrics.conversions "
                "FROM search_term_view "
                f"WHERE campaign.id = {campaign_id_limpo} "
                f"AND segments.date DURING LAST_{dias}_DAYS"
            )
            response = googleads_service.search(customer_id=customer_id_limpo, query=query)

            termos: list[dict[str, Any]] = []
            for row in response:
                termo = str(getattr(row.search_term_view, "search_term", "") or "").strip()
                if not termo:
                    continue
                termos.append(
                    {
                        "search_term": termo,
                        "date": str(getattr(row.segments, "date", "") or ""),
                        "clicks": int(getattr(row.metrics, "clicks", 0) or 0),
                        "impressions": int(getattr(row.metrics, "impressions", 0) or 0),
                        "cost": float(getattr(row.metrics, "cost_micros", 0) or 0) / 1_000_000.0,
                        "conversions": int(float(getattr(row.metrics, "conversions", 0) or 0)),
                        "ad_group_id": str(getattr(row.ad_group, "id", "") or ""),
                        "nome_servico": str(getattr(row.ad_group, "name", "") or ""),
                    }
                )
            for item in termos:
                clicks = int(item.get("clicks", 0) or 0)
                impressions = int(item.get("impressions", 0) or 0)
                item["ctr"] = (float(clicks) / float(impressions) * 100.0) if impressions > 0 else 0.0
            logger.info(
                "Search terms coletados. customer_id=%s campaign_id=%s total=%s",
                customer_id_limpo,
                campaign_id_limpo,
                len(termos),
            )
            return termos
        except GoogleAdsException:
            logger.exception(
                "Falha GoogleAdsException ao coletar search terms. customer_id=%s campaign_id=%s",
                customer_id_limpo,
                campaign_id_limpo,
            )
            return []
        except Exception:
            logger.exception(
                "Falha inesperada ao coletar search terms. customer_id=%s campaign_id=%s",
                customer_id_limpo,
                campaign_id_limpo,
            )
            return []

    def fetch_device_performance(
        self,
        customer_id: str,
        campaign_id: str,
        periodo_dias: int = 15,
        credentials_dict: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        campaign_id_limpo = (campaign_id or "").strip()
        dias = max(1, int(periodo_dias or 15))
        try:
            if not credentials_dict:
                raise ValueError("credentials_dict e obrigatorio para consultar campaign_device_view.")
            client = self._build_google_client(credentials_dict)
            googleads_service = client.get_service("GoogleAdsService")
            query = (
                "SELECT "
                "segments.device, "
                "metrics.clicks, "
                "metrics.impressions, "
                "metrics.cost_micros, "
                "metrics.conversions "
                "FROM campaign_device_view "
                f"WHERE campaign.id = {campaign_id_limpo} "
                f"AND segments.date DURING LAST_{dias}_DAYS"
            )
            response = googleads_service.search(customer_id=customer_id_limpo, query=query)
            resultado: dict[str, dict[str, Any]] = {}
            for row in response:
                device_raw = str(getattr(row.segments, "device", "") or "").strip().upper() or "UNSPECIFIED"
                clicks = int(getattr(row.metrics, "clicks", 0) or 0)
                impressions = int(getattr(row.metrics, "impressions", 0) or 0)
                cost = float(getattr(row.metrics, "cost_micros", 0) or 0) / 1_000_000.0
                conversions = float(getattr(row.metrics, "conversions", 0) or 0.0)
                if device_raw not in resultado:
                    resultado[device_raw] = {
                        "device": device_raw,
                        "clicks": 0,
                        "impressions": 0,
                        "cost": 0.0,
                        "conversions": 0.0,
                    }
                resultado[device_raw]["clicks"] += clicks
                resultado[device_raw]["impressions"] += impressions
                resultado[device_raw]["cost"] += cost
                resultado[device_raw]["conversions"] += conversions

            dispositivos = []
            for item in resultado.values():
                conv = float(item["conversions"] or 0.0)
                cost = float(item["cost"] or 0.0)
                item["cpa"] = (cost / conv) if conv > 0 else None
                item["ctr"] = (
                    (float(item["clicks"]) / float(item["impressions"])) * 100.0 if int(item["impressions"] or 0) > 0 else 0.0
                )
                item["cost"] = round(cost, 4)
                item["conversions"] = round(conv, 2)
                if item["cpa"] is not None:
                    item["cpa"] = round(float(item["cpa"]), 4)
                item["ctr"] = round(float(item["ctr"]), 4)
                dispositivos.append(item)
            dispositivos.sort(key=lambda d: float(d.get("cost", 0.0)), reverse=True)
            logger.info(
                "Device performance coletada. customer_id=%s campaign_id=%s total_devices=%s",
                customer_id_limpo,
                campaign_id_limpo,
                len(dispositivos),
            )
            return dispositivos
        except Exception:
            logger.exception(
                "Falha ao coletar performance por dispositivo. customer_id=%s campaign_id=%s",
                customer_id_limpo,
                campaign_id_limpo,
            )
            return []

    def fetch_hourly_performance(
        self,
        customer_id: str,
        campaign_id: str,
        periodo_dias: int = 15,
        credentials_dict: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        campaign_id_limpo = (campaign_id or "").strip()
        dias = max(1, int(periodo_dias or 15))
        try:
            if not credentials_dict:
                raise ValueError("credentials_dict e obrigatorio para consultar performance por horario.")
            client = self._build_google_client(credentials_dict)
            googleads_service = client.get_service("GoogleAdsService")
            query = (
                "SELECT "
                "segments.hour, "
                "segments.day_of_week, "
                "metrics.clicks, "
                "metrics.cost_micros, "
                "metrics.conversions "
                "FROM campaign "
                f"WHERE campaign.id = {campaign_id_limpo} "
                f"AND segments.date DURING LAST_{dias}_DAYS"
            )
            response = googleads_service.search(customer_id=customer_id_limpo, query=query)
            agregado: dict[str, dict[str, Any]] = {}
            for row in response:
                hora = int(getattr(row.segments, "hour", 0) or 0)
                dia_semana = str(getattr(row.segments, "day_of_week", "") or "").strip().upper() or "UNSPECIFIED"
                chave = f"{dia_semana}:{hora}"
                if chave not in agregado:
                    agregado[chave] = {
                        "hour_of_day": hora,
                        "day_of_week": dia_semana,
                        "clicks": 0,
                        "cost": 0.0,
                        "conversions": 0.0,
                    }
                agregado[chave]["clicks"] += int(getattr(row.metrics, "clicks", 0) or 0)
                agregado[chave]["cost"] += float(getattr(row.metrics, "cost_micros", 0) or 0) / 1_000_000.0
                agregado[chave]["conversions"] += float(getattr(row.metrics, "conversions", 0) or 0.0)
            horarios = list(agregado.values())
            for item in horarios:
                conv = float(item.get("conversions", 0.0) or 0.0)
                cost = float(item.get("cost", 0.0) or 0.0)
                item["cpa"] = (cost / conv) if conv > 0 else None
                item["cost"] = round(cost, 4)
                item["conversions"] = round(conv, 2)
                if item["cpa"] is not None:
                    item["cpa"] = round(float(item["cpa"]), 4)
            horarios.sort(key=lambda x: (str(x.get("day_of_week", "")), int(x.get("hour_of_day", 0))))
            logger.info(
                "Performance por horario coletada. customer_id=%s campaign_id=%s total_slots=%s",
                customer_id_limpo,
                campaign_id_limpo,
                len(horarios),
            )
            return horarios
        except Exception:
            logger.exception(
                "Falha ao coletar performance por horario. customer_id=%s campaign_id=%s",
                customer_id_limpo,
                campaign_id_limpo,
            )
            return []
