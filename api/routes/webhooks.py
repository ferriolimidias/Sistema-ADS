import hashlib
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import get_db
from models.schema import Campanha, Cliente, ConversaoAgenteSO, FerrioliConfig, MetricasDiarias
from engines.google_engine.offline_conversions import GoogleOfflineConnector
from engines.meta_engine.capi import MetaCAPIConnector

router = APIRouter(tags=["webhooks"])
logger = logging.getLogger(__name__)


def _incrementar_receita_metricas_diarias(db, campanha_id: int, valor_venda: Optional[float]) -> None:
    valor = float(valor_venda or 0.0)
    hoje = datetime.utcnow().date()
    row = (
        db.query(MetricasDiarias)
        .filter(
            MetricasDiarias.campanha_id == campanha_id,
            MetricasDiarias.data == hoje,
        )
        .first()
    )
    if row:
        row.receita = float(row.receita or 0.0) + valor
    else:
        db.add(
            MetricasDiarias(
                campanha_id=campanha_id,
                data=hoje,
                spend=0.0,
                conversoes=0,
                receita=valor,
            )
        )


class ConversaoAgenteSOPayload(BaseModel):
    telefone: str
    tag_aplicada: str
    campanha_id: Optional[int] = None
    gclid: Optional[str] = None
    fbclid: Optional[str] = None
    valor_venda: Optional[float] = None


@router.post("/agenteso/conversao")
def registrar_conversao_agenteso(
    payload: ConversaoAgenteSOPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    campanha = None
    if payload.campanha_id:
        campanha = (
            db.query(Campanha)
            .join(Cliente, Campanha.cliente_id == Cliente.id)
            .filter(
                Campanha.id == payload.campanha_id,
                Cliente.status_ativo.is_(True),
            )
            .first()
        )
    else:
        campanha = (
            db.query(Campanha)
            .join(Cliente, Campanha.cliente_id == Cliente.id)
            .filter(Cliente.status_ativo.is_(True))
            .first()
        )

    cliente = campanha.cliente if campanha else None
    telefone_hash = hashlib.sha256(payload.telefone.encode("utf-8")).hexdigest()

    conversao = ConversaoAgenteSO(
        cliente_id=cliente.id if cliente else None,
        telefone_hash=telefone_hash,
        tag_aplicada=payload.tag_aplicada,
        gclid=payload.gclid,
        fbclid=payload.fbclid,
        valor_venda=payload.valor_venda,
    )
    db.add(conversao)
    if campanha:
        _incrementar_receita_metricas_diarias(db, campanha.id, payload.valor_venda)
    db.commit()
    db.refresh(conversao)

    ferrioli_config = db.query(FerrioliConfig).first()

    if not ferrioli_config:
        logger.warning("Nenhuma configuracao master encontrada em Ferrioli_Config.")
    if not campanha:
        logger.warning("Nenhuma campanha associada encontrada para rotear a conversao.")

    valor_venda = payload.valor_venda or 0.0

    if ferrioli_config and campanha and cliente and (payload.fbclid or payload.telefone):
        if ferrioli_config.meta_bm_token and campanha.meta_pixel_id:
            background_tasks.add_task(
                MetaCAPIConnector().enviar_evento_conversao,
                telefone=payload.telefone,
                valor=valor_venda,
                token=ferrioli_config.meta_bm_token,
                pixel_id=campanha.meta_pixel_id,
            )
        else:
            logger.warning(
                "Dados insuficientes para envio Meta CAPI. campanha_id=%s",
                campanha.id,
            )

    if ferrioli_config and campanha and cliente and payload.gclid:
        google_credentials = {
            "developer_token": ferrioli_config.google_mcc_token,
            "client_id": ferrioli_config.google_ads_client_id,
            "client_secret": ferrioli_config.google_ads_client_secret,
            "refresh_token": ferrioli_config.google_ads_refresh_token,
            "use_client_customer_id": ferrioli_config.google_ads_use_client_customer_id,
        }

        if all(
            [
                google_credentials["developer_token"],
                google_credentials["client_id"],
                google_credentials["client_secret"],
                google_credentials["refresh_token"],
                cliente.google_customer_id,
                campanha.google_conversion_action_id,
            ]
        ):
            background_tasks.add_task(
                GoogleOfflineConnector().enviar_click_conversion,
                gclid=payload.gclid,
                valor=valor_venda,
                customer_id=cliente.google_customer_id,
                conversion_action_id=campanha.google_conversion_action_id,
                credentials_dict=google_credentials,
            )
        else:
            logger.warning(
                "Dados insuficientes para envio Google Offline Conversion. campanha_id=%s",
                campanha.id,
            )

    return {"status": "sucesso", "mensagem": "Conversão registrada"}
