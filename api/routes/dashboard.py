from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload, selectinload

from models.database import get_db
from models.schema import Campanha, Cliente, LogOtimizacaoGECO

router = APIRouter(prefix="/admin")


class ClienteResponse(BaseModel):
    id: int
    nome: str
    cnpj: str
    google_customer_id: Optional[str] = None
    meta_ad_account_id: Optional[str] = None
    status_ativo: bool


class CampanhaResponse(BaseModel):
    id: int
    cliente_id: int
    cliente_nome: str
    id_plataforma: str
    plataforma: str
    tipo: str
    status: str
    orcamento_diario: float
    roas_alvo: Optional[float] = None
    cpa_alvo: Optional[float] = None
    meta_pixel_id: Optional[str] = None
    google_conversion_action_id: Optional[str] = None
    plataforma_campanha_id: Optional[str] = None
    url_slug: Optional[str] = None


class LogGecoResponse(BaseModel):
    id: int
    campanha_id: int
    campanha_id_plataforma: str
    campanha_plataforma: str
    acao_tomada: str
    motivo: str
    metricas_no_momento: dict[str, Any]
    data_criacao: datetime


class CampanhaUpdateRequest(BaseModel):
    cpa_alvo: Optional[float] = Field(default=None, gt=0, description="O CPA alvo deve ser maior que zero")
    orcamento_diario: Optional[float] = Field(default=None, gt=0, description="O orçamento deve ser maior que zero")
    meta_pixel_id: Optional[str] = None
    google_conversion_action_id: Optional[str] = None


def _serializar_campanha(campanha: Campanha) -> CampanhaResponse:
    return CampanhaResponse(
        id=campanha.id,
        cliente_id=campanha.cliente_id,
        cliente_nome=campanha.cliente.nome if campanha.cliente else "",
        id_plataforma=campanha.id_plataforma,
        plataforma=campanha.plataforma,
        tipo=campanha.tipo,
        status=campanha.status,
        orcamento_diario=campanha.orcamento_diario,
        roas_alvo=campanha.roas_alvo,
        cpa_alvo=campanha.cpa_alvo,
        meta_pixel_id=campanha.meta_pixel_id,
        google_conversion_action_id=campanha.google_conversion_action_id,
        plataforma_campanha_id=campanha.plataforma_campanha_id,
        url_slug=campanha.landing_pages[0].url_slug if campanha.landing_pages else None,
    )


@router.get("/clientes", response_model=list[ClienteResponse])
def listar_clientes(db: Session = Depends(get_db)):
    clientes = db.query(Cliente).all()
    return [
        ClienteResponse(
            id=cliente.id,
            nome=cliente.nome,
            cnpj=cliente.cnpj,
            google_customer_id=cliente.google_customer_id,
            meta_ad_account_id=cliente.meta_ad_account_id,
            status_ativo=cliente.status_ativo,
        )
        for cliente in clientes
    ]


@router.get("/campanhas", response_model=list[CampanhaResponse])
def listar_campanhas(db: Session = Depends(get_db)):
    campanhas = (
        db.query(Campanha)
        .options(joinedload(Campanha.cliente), selectinload(Campanha.landing_pages))
        .all()
    )

    return [_serializar_campanha(campanha) for campanha in campanhas]


@router.get("/logs-geco", response_model=list[LogGecoResponse])
def listar_logs_geco(db: Session = Depends(get_db)):
    logs = (
        db.query(LogOtimizacaoGECO)
        .options(joinedload(LogOtimizacaoGECO.campanha))
        .order_by(LogOtimizacaoGECO.data_criacao.desc())
        .limit(50)
        .all()
    )

    return [
        LogGecoResponse(
            id=log.id,
            campanha_id=log.campanha_id,
            campanha_id_plataforma=log.campanha.id_plataforma if log.campanha else "",
            campanha_plataforma=log.campanha.plataforma if log.campanha else "",
            acao_tomada=log.acao_tomada,
            motivo=log.motivo,
            metricas_no_momento=log.metricas_no_momento,
            data_criacao=log.data_criacao,
        )
        for log in logs
    ]


@router.put("/campanhas/{campanha_id}", response_model=CampanhaResponse)
def atualizar_campanha(
    campanha_id: int,
    payload: CampanhaUpdateRequest,
    db: Session = Depends(get_db),
):
    campanha = (
        db.query(Campanha)
        .options(joinedload(Campanha.cliente), selectinload(Campanha.landing_pages))
        .filter(Campanha.id == campanha_id)
        .first()
    )
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")

    update_data = payload.model_dump(exclude_unset=True)
    if payload.meta_pixel_id is not None:
        update_data["meta_pixel_id"] = payload.meta_pixel_id.strip()
    if payload.google_conversion_action_id is not None:
        update_data["google_conversion_action_id"] = payload.google_conversion_action_id.strip()

    for field_name, field_value in update_data.items():
        setattr(campanha, field_name, field_value)

    db.commit()
    db.refresh(campanha)

    campanha = (
        db.query(Campanha)
        .options(joinedload(Campanha.cliente), selectinload(Campanha.landing_pages))
        .filter(Campanha.id == campanha_id)
        .first()
    )
    return _serializar_campanha(campanha)
