import hashlib
import logging
import re
import time

from facebook_business.adobjects.serverside.custom_data import CustomData
from facebook_business.adobjects.serverside.event_request import EventRequest
from facebook_business.adobjects.serverside.server_event import ServerEvent
from facebook_business.adobjects.serverside.user_data import UserData

logger = logging.getLogger(__name__)


class MetaCAPIConnector:
    @staticmethod
    def _normalizar_telefone(telefone: str) -> str:
        return re.sub(r"\D", "", telefone or "")

    @staticmethod
    def _hash_sha256(valor: str) -> str:
        return hashlib.sha256(valor.encode("utf-8")).hexdigest()

    def enviar_evento_conversao(
        self,
        telefone: str,
        valor: float,
        token: str,
        pixel_id: str,
        event_name: str = "Purchase",
    ):
        try:
            telefone_limpo = self._normalizar_telefone(telefone)
            if not telefone_limpo:
                raise ValueError("Telefone invalido: nao foi possivel extrair numeros.")

            telefone_hash = self._hash_sha256(telefone_limpo)
            user_data = UserData(ph=[telefone_hash])
            custom_data = CustomData(value=float(valor), currency="BRL")
            evento = ServerEvent(
                event_name=event_name,
                event_time=int(time.time()),
                user_data=user_data,
                custom_data=custom_data,
                action_source="system_generated",
            )

            request = EventRequest(
                pixel_id=pixel_id,
                events=[evento],
                access_token=token,
            )

            response = request.execute()
            logger.info(
                "Evento Meta CAPI enviado com sucesso. pixel_id=%s event_name=%s",
                pixel_id,
                event_name,
            )
            return response
        except Exception:
            logger.exception(
                "Falha ao enviar evento para Meta CAPI. pixel_id=%s event_name=%s",
                pixel_id,
                event_name,
            )
            return None
