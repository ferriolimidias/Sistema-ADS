import logging
import time

from facebook_business.adobjects.campaign import Campaign

logger = logging.getLogger(__name__)


class MetaAdsLauncher:
    def pausar_campanha(self, plataforma_campanha_id: str, credentials_dict: dict):
        try:
            token = (credentials_dict or {}).get("meta_bm_token")
            if not token:
                raise ValueError("Token Meta nao informado para pausar campanha.")

            logger.info(
                "Mock de pausa Meta iniciado. plataforma_campanha_id=%s",
                plataforma_campanha_id,
            )

            # Fluxo real a ser habilitado apos validacao em ambiente seguro:
            # from facebook_business.api import FacebookAdsApi
            # FacebookAdsApi.init(access_token=token)
            # campaign = Campaign(plataforma_campanha_id)
            # campaign.api_update(fields=[], params={"status": "PAUSED"})

            # Mantido como mock seguro para evitar pausas reais durante testes locais.
            _campaign = Campaign(plataforma_campanha_id)
            _ = _campaign
            time.sleep(1)

            logger.info(
                "Mock de pausa Meta finalizado com sucesso. plataforma_campanha_id=%s",
                plataforma_campanha_id,
            )
            return True
        except Exception:
            logger.exception(
                "Falha ao pausar campanha Meta. plataforma_campanha_id=%s",
                plataforma_campanha_id,
            )
            return False
