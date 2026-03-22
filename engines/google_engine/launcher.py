import asyncio
import logging

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.api_core import protobuf_helpers

logger = logging.getLogger(__name__)


class GoogleAdsLauncher:
    async def criar_campanha_pesquisa(
        self,
        credentials_dict: dict,
        customer_id: str,
        orcamento_diario: float,
        url_final: str,
        copy_data: dict,
    ):
        logger.info(
            "Mock de criacao de campanha Google Ads iniciado. customer_id=%s orcamento_diario=%s url_final=%s headlines=%s descriptions=%s",
            customer_id,
            orcamento_diario,
            url_final,
            len(copy_data.get("headlines", [])),
            len(copy_data.get("descriptions", [])),
        )
        logger.debug(
            "Dados recebidos para criacao mock de campanha Google Ads. credentials_keys=%s copy_data=%s",
            list(credentials_dict.keys()),
            copy_data,
        )

        await asyncio.sleep(2)

        campanha_id = "mock_google_id_9999"
        logger.info(
            "Mock de criacao de campanha Google Ads finalizado. customer_id=%s plataforma_campanha_id=%s",
            customer_id,
            campanha_id,
        )
        return campanha_id

    async def pausar_campanha(
        self,
        customer_id: str,
        plataforma_campanha_id: str,
        credentials_dict: dict,
    ):
        logger.info(
            "Mock de pausa Google Ads iniciado. customer_id=%s plataforma_campanha_id=%s credenciais=%s",
            customer_id,
            plataforma_campanha_id,
            list((credentials_dict or {}).keys()),
        )

        # Fluxo real sera implementado com CampaignOperation + CampaignService
        # usando update via FieldMask para alterar o status para PAUSED.
        await asyncio.sleep(1)

        logger.info(
            "Mock de pausa Google Ads finalizado com sucesso. customer_id=%s plataforma_campanha_id=%s",
            customer_id,
            plataforma_campanha_id,
        )
        return True

    async def atualizar_orcamento_diario(
        self,
        customer_id: str,
        plataforma_campanha_id: str,
        novo_valor: float,
        credentials_dict: dict,
    ):
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        campanha_id_limpo = (plataforma_campanha_id or "").strip()

        try:
            google_ads_config = dict(credentials_dict or {})
            use_client_customer_id = google_ads_config.pop("use_client_customer_id", None)
            if use_client_customer_id:
                google_ads_config["login_customer_id"] = str(use_client_customer_id).replace("-", "").strip()

            client = GoogleAdsClient.load_from_dict(google_ads_config)
            googleads_service = client.get_service("GoogleAdsService")
            campaign_budget_service = client.get_service("CampaignBudgetService")

            query = (
                "SELECT campaign.campaign_budget "
                f"FROM campaign WHERE campaign.id = {campanha_id_limpo}"
            )
            response = googleads_service.search(customer_id=customer_id_limpo, query=query)

            budget_resource_name = None
            for row in response:
                budget_resource_name = row.campaign.campaign_budget
                break

            if not budget_resource_name:
                raise ValueError("Nao foi possivel localizar o resource name do orcamento da campanha.")

            budget_operation = client.get_type("CampaignBudgetOperation")
            budget_operation.update.resource_name = budget_resource_name
            budget_operation.update.amount_micros = int(novo_valor * 1000000)
            client.copy_from(
                budget_operation.update_mask,
                protobuf_helpers.field_mask(None, budget_operation.update._pb),
            )

            campaign_budget_service.mutate_campaign_budgets(
                customer_id=customer_id_limpo,
                operations=[budget_operation],
            )

            logger.info(
                "Orcamento Google Ads atualizado com sucesso. customer_id=%s plataforma_campanha_id=%s novo_valor=%.2f",
                customer_id_limpo,
                campanha_id_limpo,
                novo_valor,
            )
            return True
        except GoogleAdsException:
            logger.exception(
                "Falha GoogleAdsException ao atualizar orcamento Google Ads. customer_id=%s plataforma_campanha_id=%s",
                customer_id_limpo,
                campanha_id_limpo,
            )
            return False
        except Exception:
            logger.exception(
                "Falha inesperada ao atualizar orcamento Google Ads. customer_id=%s plataforma_campanha_id=%s",
                customer_id_limpo,
                campanha_id_limpo,
            )
            return False
