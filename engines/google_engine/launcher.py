import asyncio
import logging

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
