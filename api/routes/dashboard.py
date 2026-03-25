import asyncio
from datetime import datetime, timedelta
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from api.utils.audit import registrar_log_safe
from engines.ai_engine.strategist import (
    analisar_performance_horarios,
    analisar_performance_dispositivos,
    analisar_termos_sujos,
    gerar_insight_estrategico,
    montar_dados_performance_reais_por_servico,
)
from engines.google_engine.launcher import GoogleAdsLauncher
from engines.google_engine.metrics import GoogleMetricsCollector
from engines.meta_engine.launcher import MetaAdsLauncher
from engines.utils.asaas_service import AsaasService
from engines.utils.cloudflare_service import CloudflareService
from engines.utils.security import get_current_user, require_admin_user
from engines.utils.security import generate_temp_password, hash_password
from engines.utils.evolution_service import EvolutionService
from models.database import get_db
from models.schema import (
    AuditLog,
    Campanha,
    Cliente,
    ConfiguracaoSistema,
    ConsumoIA,
    ConversaoVenda,
    FerrioliConfig,
    LogOtimizacaoGECO,
    MetricasDiarias,
    Usuario,
    UsuarioRole,
)

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin_user)])
client_router = APIRouter(prefix="/client", dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


class ClienteResponse(BaseModel):
    id: int
    nome: str
    razao_social: Optional[str] = None
    cnpj: Optional[str] = None
    email_acesso: Optional[str] = None
    whatsapp: Optional[str] = None
    whatsapp_group_jid: Optional[str] = None
    google_customer_id: Optional[str] = None
    meta_ad_account_id: Optional[str] = None
    dominio_personalizado: Optional[str] = None
    asaas_customer_id: Optional[str] = None
    data_vencimento_licenca: Optional[datetime] = None
    status_ativo: bool


class ClienteUpdateRequest(BaseModel):
    nome: Optional[str] = None
    razao_social: Optional[str] = None
    cnpj: Optional[str] = None
    whatsapp: Optional[str] = None
    google_customer_id: Optional[str] = None
    meta_ad_account_id: Optional[str] = None
    status_ativo: Optional[bool] = None


class ClienteCobrarRequest(BaseModel):
    valor: float = Field(gt=0, description="Valor da cobranca deve ser maior que zero")
    descricao: str


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
    raio_geografico: Optional[int] = None
    endereco_negocio: Optional[str] = None
    copy_gerada: Optional[dict[str, Any]] = None
    assets_adicionais: Optional[dict[str, Any]] = None


class LogGecoResponse(BaseModel):
    id: int
    campanha_id: int
    campanha_id_plataforma: str
    campanha_plataforma: str
    acao_tomada: str
    motivo: str
    metricas_no_momento: dict[str, Any]
    data_criacao: datetime


class AuditLogResponse(BaseModel):
    id: int
    timestamp: datetime
    user_id: Optional[int] = None
    usuario_email: Optional[str] = None
    acao: str
    recurso: str
    detalhes: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None


class CampanhaUpdateRequest(BaseModel):
    cpa_alvo: Optional[float] = Field(default=None, gt=0, description="O CPA alvo deve ser maior que zero")
    orcamento_diario: Optional[float] = Field(default=None, gt=0, description="O orçamento deve ser maior que zero")
    meta_pixel_id: Optional[str] = None
    google_conversion_action_id: Optional[str] = None
    raio_geografico: Optional[int] = Field(default=None, ge=0, description="Raio geografico em km")
    endereco_negocio: Optional[str] = None
    copy_gerada: Optional[dict[str, Any]] = None
    assets_adicionais: Optional[dict[str, Any]] = None


class CampanhaAprovacaoResponse(BaseModel):
    mensagem: str
    campanha: CampanhaResponse


class PerformanceConsolidadaResponse(BaseModel):
    gasto_total: float
    receita_total: float
    roas_geral: Optional[float] = None
    total_leads: int
    breakdown_servicos: Optional[list[dict[str, Any]]] = None


class RegistrarVendaRequest(BaseModel):
    campanha_id: int
    valor: float = Field(gt=0, description="Valor da venda deve ser maior que zero")
    canal: Optional[str] = "WHATSAPP"


class OtimizarServicoRequest(BaseModel):
    campanha_id: int
    nome_servico: str
    acao: str  # PAUSAR | ESCALAR
    valor: Optional[float] = None


class AnalisarTermosRequest(BaseModel):
    campanha_id: int
    nome_servico: str
    periodo_dias: int = 7
    ad_group_id: Optional[str] = None


class NegativarTermosRequest(BaseModel):
    campanha_id: int
    nome_servico: str
    ad_group_id: str
    termos: list[str]
    periodo_dias: int = 30


class AjustarDispositivoRequest(BaseModel):
    campanha_id: int
    dispositivo: str
    ajuste_percentual: float = Field(ge=-90, le=200, description="Ajuste percentual do lance por dispositivo.")


class AjustarHorarioRequest(BaseModel):
    campanha_id: int
    dia_semana: str
    hora_inicio: int = Field(ge=0, le=23)
    hora_fim: int = Field(ge=1, le=24)
    ajuste_percentual: float = Field(ge=-90, le=200)


class ProvisionarDominioRequest(BaseModel):
    slug: str


class ClienteCreateRequest(BaseModel):
    nome: str
    razao_social: Optional[str] = None
    cnpj: Optional[str] = None
    email: str
    whatsapp: Optional[str] = None
    google_customer_id: Optional[str] = None
    meta_ad_account_id: Optional[str] = None
    status_ativo: bool = True
    criar_grupo: bool = False
    logo_url: Optional[str] = None


class ConfiguracaoResponse(BaseModel):
    id: int
    meta_bm_token: str
    meta_page_id: Optional[str] = None
    google_mcc_token: str
    google_ads_client_id: Optional[str] = None
    google_ads_client_secret: Optional[str] = None
    google_ads_refresh_token: Optional[str] = None
    google_ads_use_client_customer_id: Optional[str] = None
    Maps_api_key: Optional[str] = None
    evolution_api_url: Optional[str] = None
    evolution_api_key: Optional[str] = None
    evolution_instance_name: Optional[str] = None
    openai_api_key: str
    asaas_api_key: Optional[str] = None
    cloudflare_api_token: Optional[str] = None
    cloudflare_zone_id: Optional[str] = None
    cloudflare_cname_target: Optional[str] = None
    razao_social: Optional[str] = None
    cnpj: Optional[str] = None
    whatsapp: Optional[str] = None


class ConfiguracaoUpdateRequest(BaseModel):
    meta_bm_token: Optional[str] = None
    meta_page_id: Optional[str] = None
    google_mcc_token: Optional[str] = None
    google_ads_client_id: Optional[str] = None
    google_ads_client_secret: Optional[str] = None
    google_ads_refresh_token: Optional[str] = None
    google_ads_use_client_customer_id: Optional[str] = None
    Maps_api_key: Optional[str] = None
    evolution_api_url: Optional[str] = None
    evolution_api_key: Optional[str] = None
    evolution_instance_name: Optional[str] = None
    openai_api_key: Optional[str] = None
    asaas_api_key: Optional[str] = None
    cloudflare_api_token: Optional[str] = None
    cloudflare_zone_id: Optional[str] = None
    cloudflare_cname_target: Optional[str] = None
    razao_social: Optional[str] = None
    cnpj: Optional[str] = None
    whatsapp: Optional[str] = None


class ConfiguracaoSistemaResponse(BaseModel):
    id: int
    intraday_cleaner_enabled: bool
    admin_whatsapp_number: Optional[str] = None


class ConfiguracaoSistemaUpdateRequest(BaseModel):
    intraday_cleaner_enabled: Optional[bool] = None
    admin_whatsapp_number: Optional[str] = None


def _montar_google_credentials(ferrioli_config: FerrioliConfig) -> dict:
    return {
        "developer_token": ferrioli_config.google_mcc_token,
        "client_id": ferrioli_config.google_ads_client_id,
        "client_secret": ferrioli_config.google_ads_client_secret,
        "refresh_token": ferrioli_config.google_ads_refresh_token,
        "use_client_customer_id": ferrioli_config.google_ads_use_client_customer_id,
    }


def _montar_meta_credentials(ferrioli_config: FerrioliConfig) -> dict:
    return {
        "meta_bm_token": ferrioli_config.meta_bm_token,
    }


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
        raio_geografico=campanha.raio_geografico,
        endereco_negocio=campanha.endereco_negocio,
        copy_gerada=campanha.copy_gerada,
        assets_adicionais=campanha.assets_adicionais,
    )


def _serializar_cliente(cliente: Cliente) -> ClienteResponse:
    return ClienteResponse(
        id=cliente.id,
        nome=cliente.nome,
        razao_social=cliente.razao_social,
        cnpj=cliente.cnpj,
        email_acesso=(cliente.usuario.email if cliente.usuario else None),
        whatsapp=cliente.whatsapp,
        whatsapp_group_jid=cliente.whatsapp_group_jid,
        google_customer_id=cliente.google_customer_id,
        meta_ad_account_id=cliente.meta_ad_account_id,
        dominio_personalizado=cliente.dominio_personalizado,
        asaas_customer_id=cliente.asaas_customer_id,
        data_vencimento_licenca=cliente.data_vencimento_licenca,
        status_ativo=cliente.status_ativo,
    )


def _serializar_configuracao(config: FerrioliConfig, cliente_padrao: Optional[Cliente] = None) -> ConfiguracaoResponse:
    return ConfiguracaoResponse(
        id=config.id,
        meta_bm_token=config.meta_bm_token,
        meta_page_id=config.meta_page_id,
        google_mcc_token=config.google_mcc_token,
        google_ads_client_id=config.google_ads_client_id,
        google_ads_client_secret=config.google_ads_client_secret,
        google_ads_refresh_token=config.google_ads_refresh_token,
        google_ads_use_client_customer_id=config.google_ads_use_client_customer_id,
        Maps_api_key=config.Maps_api_key,
        evolution_api_url=config.evolution_api_url,
        evolution_api_key=config.evolution_api_key,
        evolution_instance_name=config.evolution_instance_name,
        openai_api_key=config.openai_api_key,
        asaas_api_key=config.asaas_api_key,
        cloudflare_api_token=config.cloudflare_api_token,
        cloudflare_zone_id=config.cloudflare_zone_id,
        cloudflare_cname_target=config.cloudflare_cname_target,
        razao_social=(cliente_padrao.razao_social if cliente_padrao else None),
        cnpj=(cliente_padrao.cnpj if cliente_padrao else None),
        whatsapp=(cliente_padrao.whatsapp if cliente_padrao else None),
    )


def _obter_ou_criar_configuracao_sistema(db: Session) -> ConfiguracaoSistema:
    config = db.query(ConfiguracaoSistema).filter(ConfiguracaoSistema.id == 1).first()
    if config:
        return config
    config = ConfiguracaoSistema(
        id=1,
        intraday_cleaner_enabled=False,
        admin_whatsapp_number=None,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.get("/configuracoes", response_model=ConfiguracaoResponse)
def obter_configuracoes(db: Session = Depends(get_db)):
    config = db.query(FerrioliConfig).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuracao master nao encontrada.")
    cliente_padrao = (
        db.query(Cliente).filter(Cliente.status_ativo.is_(True)).order_by(Cliente.id.asc()).first()
        or db.query(Cliente).order_by(Cliente.id.asc()).first()
    )
    return _serializar_configuracao(config, cliente_padrao)


@router.put("/configuracoes", response_model=ConfiguracaoResponse)
def atualizar_configuracoes(
    payload: ConfiguracaoUpdateRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = db.query(FerrioliConfig).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuracao master nao encontrada.")
    cliente_padrao = (
        db.query(Cliente).filter(Cliente.status_ativo.is_(True)).order_by(Cliente.id.asc()).first()
        or db.query(Cliente).order_by(Cliente.id.asc()).first()
    )

    update_data = payload.model_dump(exclude_unset=True)
    for field_name in [
        "meta_bm_token",
        "meta_page_id",
        "google_mcc_token",
        "google_ads_client_id",
        "google_ads_client_secret",
        "google_ads_refresh_token",
        "google_ads_use_client_customer_id",
        "Maps_api_key",
        "evolution_api_url",
        "evolution_api_key",
        "evolution_instance_name",
        "openai_api_key",
        "asaas_api_key",
        "cloudflare_api_token",
        "cloudflare_zone_id",
        "cloudflare_cname_target",
        "razao_social",
        "cnpj",
        "whatsapp",
    ]:
        if field_name in update_data and isinstance(update_data[field_name], str):
            update_data[field_name] = update_data[field_name].strip()

    for field_name, field_value in update_data.items():
        if field_name in {"razao_social", "cnpj", "whatsapp"}:
            if cliente_padrao:
                setattr(cliente_padrao, field_name, field_value)
            continue
        setattr(config, field_name, field_value)

    db.commit()
    db.refresh(config)
    if cliente_padrao:
        db.refresh(cliente_padrao)

    if update_data:
        try:
            registrar_log_safe(
                db=db,
                user_id=current_user.id,
                acao="ALTERAR_CONFIGURACOES",
                recurso="Configuracoes Globais",
                detalhes={"campos_alterados": sorted(update_data.keys())},
                request=request,
            )
        except Exception:
            pass
    return _serializar_configuracao(config, cliente_padrao)


@router.get("/configuracoes-sistema", response_model=ConfiguracaoSistemaResponse)
def obter_configuracoes_sistema(db: Session = Depends(get_db)):
    config = _obter_ou_criar_configuracao_sistema(db=db)
    return ConfiguracaoSistemaResponse(
        id=config.id,
        intraday_cleaner_enabled=bool(config.intraday_cleaner_enabled),
        admin_whatsapp_number=config.admin_whatsapp_number,
    )


@router.put("/configuracoes-sistema", response_model=ConfiguracaoSistemaResponse)
def atualizar_configuracoes_sistema(
    payload: ConfiguracaoSistemaUpdateRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = _obter_ou_criar_configuracao_sistema(db=db)
    update_data = payload.model_dump(exclude_unset=True)
    if "admin_whatsapp_number" in update_data and isinstance(update_data["admin_whatsapp_number"], str):
        update_data["admin_whatsapp_number"] = update_data["admin_whatsapp_number"].strip() or None

    for field_name, field_value in update_data.items():
        setattr(config, field_name, field_value)

    db.commit()
    db.refresh(config)

    if update_data:
        try:
            registrar_log_safe(
                db=db,
                user_id=current_user.id,
                acao="ALTERAR_CONFIG_SISTEMA",
                recurso="ConfiguracaoSistema",
                detalhes={"campos_alterados": sorted(update_data.keys())},
                request=request,
            )
        except Exception:
            pass

    return ConfiguracaoSistemaResponse(
        id=config.id,
        intraday_cleaner_enabled=bool(config.intraday_cleaner_enabled),
        admin_whatsapp_number=config.admin_whatsapp_number,
    )


@router.get("/clientes", response_model=list[ClienteResponse])
def listar_clientes(db: Session = Depends(get_db)):
    clientes = db.query(Cliente).order_by(Cliente.id.desc()).all()
    return [_serializar_cliente(cliente) for cliente in clientes]


@router.put("/clientes/{cliente_id}", response_model=ClienteResponse)
def atualizar_cliente(
    cliente_id: int,
    payload: ClienteUpdateRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")

    update_data = payload.model_dump(exclude_unset=True)
    campos_string = {"nome", "razao_social", "cnpj", "whatsapp", "google_customer_id", "meta_ad_account_id"}
    campos_nullable = {"razao_social", "cnpj", "whatsapp", "google_customer_id", "meta_ad_account_id"}
    for field_name in campos_string:
        if field_name in update_data and isinstance(update_data[field_name], str):
            valor_limpo = update_data[field_name].strip()
            update_data[field_name] = valor_limpo if (valor_limpo or field_name not in campos_nullable) else None

    for field_name, field_value in update_data.items():
        setattr(cliente, field_name, field_value)

    db.commit()
    db.refresh(cliente)

    if update_data:
        try:
            registrar_log_safe(
                db=db,
                user_id=current_user.id,
                acao="ATUALIZAR_CLIENTE",
                recurso=f"Cliente #{cliente.id}",
                detalhes={"campos_alterados": sorted(update_data.keys())},
                request=request,
            )
        except Exception:
            pass

    return _serializar_cliente(cliente)


@router.post("/infra/provisionar-dominio/{cliente_id}")
def provisionar_dominio_cliente(
    cliente_id: int,
    payload: ProvisionarDominioRequest,
    request: Request,
    current_user: Usuario = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")

    config = db.query(FerrioliConfig).first()
    if not config:
        raise HTTPException(status_code=500, detail="Configuracao master nao encontrada.")

    slug = str(payload.slug or "").strip().lower()
    if not slug:
        raise HTTPException(status_code=400, detail="Slug obrigatorio para provisionar dominio.")

    try:
        cf_result = CloudflareService().criar_subdominio_cname(slug=slug, config=config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao criar DNS na Cloudflare: {exc}") from exc

    status_code = int(cf_result.get("status_code", 500))
    payload_cf = cf_result.get("payload", {})
    if status_code >= 400 or not bool((payload_cf or {}).get("success", True)):
        raise HTTPException(
            status_code=502,
            detail={
                "mensagem": "Cloudflare retornou erro ao provisionar dominio.",
                "cloudflare_status_code": status_code,
                "cloudflare_payload": payload_cf,
            },
        )

    resposta_cf = payload_cf if isinstance(payload_cf, dict) else {}
    zone_name = str((resposta_cf.get("result", {}) or {}).get("zone_name", "dominio.com")).strip() or "dominio.com"
    dominio_final = f"{slug}.{zone_name}"
    cliente.dominio_personalizado = dominio_final
    db.commit()
    db.refresh(cliente)

    try:
        registrar_log_safe(
            db=db,
            user_id=current_user.id,
            acao="PROVISIONAR_DOMINIO",
            recurso=f"Cliente #{cliente.id}",
            detalhes={
                "slug": slug,
                "dominio_personalizado": dominio_final,
                "cloudflare_status_code": status_code,
            },
            request=request,
        )
    except Exception:
        pass

    return {
        "status": "sucesso",
        "cliente_id": cliente.id,
        "dominio_personalizado": dominio_final,
        "cloudflare": cf_result,
    }


@router.post("/clientes/{cliente_id}/cobrar")
def cobrar_cliente(
    cliente_id: int,
    payload: ClienteCobrarRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")

    config = db.query(FerrioliConfig).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuracao master nao encontrada.")

    asaas_api_key = str(config.asaas_api_key or "").strip()
    if not asaas_api_key:
        raise HTTPException(status_code=400, detail="Asaas API Key nao configurada.")

    descricao = str(payload.descricao or "").strip()
    if not descricao:
        raise HTTPException(status_code=400, detail="Descricao obrigatoria para gerar cobranca.")

    asaas_service = AsaasService()
    if not cliente.asaas_customer_id:
        try:
            novo_cliente_asaas = asaas_service.criar_cliente(
                api_key=asaas_api_key,
                nome=cliente.nome,
                cpf_cnpj=cliente.cnpj,
                email=(cliente.usuario.email if cliente.usuario else None),
                telefone=cliente.whatsapp,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Falha ao criar cliente no Asaas: {exc}") from exc

        asaas_customer_id = str(novo_cliente_asaas.get("id") or "").strip()
        if not asaas_customer_id:
            raise HTTPException(status_code=502, detail="Asaas nao retornou ID do cliente.")
        cliente.asaas_customer_id = asaas_customer_id
        db.commit()
        db.refresh(cliente)

    try:
        cobranca = asaas_service.criar_cobranca_avulsa(
            api_key=asaas_api_key,
            asaas_customer_id=str(cliente.asaas_customer_id),
            valor=float(payload.valor),
            descricao=descricao,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao criar cobranca no Asaas: {exc}") from exc

    invoice_url = str(cobranca.get("invoiceUrl") or "").strip()
    if not invoice_url:
        raise HTTPException(status_code=502, detail="Asaas nao retornou URL de pagamento.")

    evolution_disponivel = all(
        [
            str(config.evolution_api_url or "").strip(),
            str(config.evolution_api_key or "").strip(),
            str(config.evolution_instance_name or "").strip(),
        ]
    )
    if cliente.whatsapp and evolution_disponivel:
        valor_formatado = (
            f"R$ {float(payload.valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        mensagem = (
            f"Ola {cliente.nome}, sua fatura referente a {descricao} no valor de {valor_formatado} foi gerada. "
            f"Acesse o link para realizar o pagamento via PIX: {invoice_url}"
        )
        try:
            EvolutionService().enviar_texto_whatsapp(
                config=config,
                numero_destino=cliente.whatsapp,
                mensagem=mensagem,
            )
        except Exception as exc:
            logger.warning("Falha ao enviar cobranca no WhatsApp para cliente_id=%s: %s", cliente.id, exc)

    try:
        registrar_log_safe(
            db=db,
            user_id=current_user.id,
            acao="GERAR_COBRANCA_CLIENTE",
            recurso=f"Cliente #{cliente.id}",
            detalhes={
                "valor": float(payload.valor),
                "descricao": descricao,
                "invoice_url": invoice_url,
                "asaas_payment_id": cobranca.get("id"),
            },
            request=request,
        )
    except Exception:
        pass

    return {"status": "sucesso", "url_pagamento": invoice_url}


@router.post("/clientes")
def criar_cliente(
    payload: ClienteCreateRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email_limpo = payload.email.strip().lower()
    if db.query(Usuario).filter(Usuario.email == email_limpo).first():
        raise HTTPException(status_code=400, detail="Ja existe um usuario com este email.")

    cliente = Cliente(
        nome=payload.nome.strip(),
        razao_social=(payload.razao_social.strip() if payload.razao_social else None),
        cnpj=(payload.cnpj.strip() if payload.cnpj else None),
        whatsapp=(payload.whatsapp.strip() if payload.whatsapp else None),
        google_customer_id=(payload.google_customer_id.strip() if payload.google_customer_id else None),
        meta_ad_account_id=(payload.meta_ad_account_id.strip() if payload.meta_ad_account_id else None),
        status_ativo=payload.status_ativo,
    )
    db.add(cliente)
    db.flush()

    senha_temporaria = generate_temp_password(8)
    usuario = Usuario(
        email=email_limpo,
        password_hash=hash_password(senha_temporaria),
        role=UsuarioRole.CLIENTE,
        needs_password_change=True,
        cliente_id=cliente.id,
    )
    db.add(usuario)
    db.commit()
    db.refresh(cliente)
    db.refresh(usuario)

    warning: Optional[str] = None
    if payload.criar_grupo:
        try:
            if not cliente.whatsapp:
                raise ValueError("WhatsApp do cliente nao informado para criacao automatica do grupo.")

            config = db.query(FerrioliConfig).first()
            if not config:
                raise ValueError("Configuracao da Evolution nao encontrada.")

            whatsapp_group_jid = EvolutionService().criar_grupo_onboarding(
                config=config,
                nome_empresa=(cliente.razao_social or cliente.nome),
                numero_cliente=cliente.whatsapp,
                logo_url=payload.logo_url,
                plataforma="Google Ads e Meta Ads",
                url_dashboard="https://seu-dominio.com/dashboard",
                email_login=usuario.email,
                senha_temporaria=senha_temporaria,
                url_login="https://seu-dominio.com/login",
            )
            cliente.whatsapp_group_jid = whatsapp_group_jid
            db.commit()
            db.refresh(cliente)
        except Exception as exc:
            logger.exception("Falha ao criar grupo de onboarding para cliente_id=%s", cliente.id)
            warning = f"Cliente salvo, mas nao foi possivel criar o grupo automaticamente: {exc}"

    try:
        registrar_log_safe(
            db=db,
            user_id=current_user.id,
            acao="CADASTRO_CLIENTE",
            recurso=f"Cliente #{cliente.id}",
            detalhes={
                "cliente_nome": cliente.nome,
                "email_acesso": usuario.email,
                "criar_grupo": bool(payload.criar_grupo),
            },
            request=request,
        )
    except Exception:
        pass

    return {
        "status": "sucesso",
        "cliente": {
            "id": cliente.id,
            "nome": cliente.nome,
            "razao_social": cliente.razao_social,
            "cnpj": cliente.cnpj,
            "email_acesso": usuario.email,
            "whatsapp": cliente.whatsapp,
            "whatsapp_group_jid": cliente.whatsapp_group_jid,
            "google_customer_id": cliente.google_customer_id,
            "meta_ad_account_id": cliente.meta_ad_account_id,
            "dominio_personalizado": cliente.dominio_personalizado,
            "status_ativo": cliente.status_ativo,
        },
        "warning": warning,
    }


@router.get("/campanhas", response_model=list[CampanhaResponse])
def listar_campanhas(cliente_id: Optional[int] = Query(default=None), db: Session = Depends(get_db)):
    query = db.query(Campanha).options(joinedload(Campanha.cliente), selectinload(Campanha.landing_pages))
    if cliente_id is not None:
        query = query.filter(Campanha.cliente_id == cliente_id)
    campanhas = query.all()

    return [_serializar_campanha(campanha) for campanha in campanhas]


@router.get("/campanhas/{campanha_id}", response_model=CampanhaResponse)
def obter_campanha(campanha_id: int, db: Session = Depends(get_db)):
    campanha = (
        db.query(Campanha)
        .options(joinedload(Campanha.cliente), selectinload(Campanha.landing_pages))
        .filter(Campanha.id == campanha_id)
        .first()
    )
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")
    return _serializar_campanha(campanha)


@router.get("/performance-consolidada", response_model=PerformanceConsolidadaResponse)
def _calcular_breakdown_servicos(
    db: Session,
    ids_campanhas: list[int],
    data_inicio: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    if not ids_campanhas:
        return []
    query = db.query(
        MetricasDiarias.campanha_id.label("campanha_id"),
        func.coalesce(MetricasDiarias.nome_servico, "SERVICO_NAO_IDENTIFICADO").label("nome_servico"),
        func.coalesce(func.sum(MetricasDiarias.spend), 0.0).label("gasto"),
        func.coalesce(func.sum(MetricasDiarias.conversoes), 0).label("conversoes"),
        func.coalesce(func.sum(MetricasDiarias.receita), 0.0).label("receita"),
    ).filter(MetricasDiarias.campanha_id.in_(ids_campanhas))
    if data_inicio:
        query = query.filter(MetricasDiarias.data >= data_inicio.date())
    rows = query.group_by(
        MetricasDiarias.campanha_id,
        func.coalesce(MetricasDiarias.nome_servico, "SERVICO_NAO_IDENTIFICADO"),
    ).all()
    breakdown = []
    for row in rows:
        gasto = float(row.gasto or 0.0)
        receita = float(row.receita or 0.0)
        conversoes = int(row.conversoes or 0)
        cpa = (gasto / conversoes) if conversoes > 0 else None
        roas = (receita / gasto) if gasto > 0 and receita > 0 else None
        breakdown.append(
            {
                "campanha_id": int(row.campanha_id),
                "nome_servico": str(row.nome_servico),
                "gasto": gasto,
                "conversoes": conversoes,
                "receita": receita,
                "cpa": (round(cpa, 2) if cpa is not None else None),
                "roas": (round(roas, 2) if roas is not None else None),
            }
        )
    breakdown.sort(key=lambda item: float(item.get("gasto") or 0.0), reverse=True)
    return breakdown


def performance_consolidada(
    cliente_id: Optional[int] = Query(default=None),
    campanha_id: Optional[int] = Query(default=None),
    incluir_servicos: bool = Query(default=False),
    periodo_dias: int = Query(default=7, ge=1, le=365),
    db: Session = Depends(get_db),
):
    data_inicio = datetime.utcnow() - timedelta(days=max(1, int(periodo_dias)) - 1)
    campanhas_query = db.query(Campanha.id, Campanha.orcamento_diario).filter(Campanha.status == "ATIVA")
    if cliente_id is not None:
        campanhas_query = campanhas_query.filter(Campanha.cliente_id == cliente_id)
    if campanha_id is not None:
        campanhas_query = campanhas_query.filter(Campanha.id == campanha_id)
    campanhas_ativas = campanhas_query.all()
    ids_ativos = [campanha.id for campanha in campanhas_ativas]
    if not ids_ativos:
        return PerformanceConsolidadaResponse(
            gasto_total=0.0,
            receita_total=0.0,
            roas_geral=None,
            total_leads=0,
            breakdown_servicos=([] if incluir_servicos else None),
        )

    # Integracao real preferencial: gasto vindo de MetricasDiarias (collector).
    gasto_real = (
        db.query(func.coalesce(func.sum(MetricasDiarias.spend), 0.0))
        .filter(MetricasDiarias.campanha_id.in_(ids_ativos))
        .filter(MetricasDiarias.data >= data_inicio.date())
        .scalar()
    )
    gasto_total = float(gasto_real or 0.0)

    # Fallback: estimativa por orcamento_diario * dias_ativos.
    if gasto_total <= 0:
        dias_por_campanha = {
            int(row[0]): int(row[1] or 0)
            for row in (
                db.query(
                    MetricasDiarias.campanha_id,
                    func.count(func.distinct(MetricasDiarias.data)),
                )
                .filter(MetricasDiarias.campanha_id.in_(ids_ativos))
                .filter(MetricasDiarias.data >= data_inicio.date())
                .group_by(MetricasDiarias.campanha_id)
                .all()
            )
        }
        gasto_total = 0.0
        for campanha in campanhas_ativas:
            dias_ativos = max(1, dias_por_campanha.get(int(campanha.id), 0))
            gasto_total += float(campanha.orcamento_diario or 0.0) * float(dias_ativos)

    receita_total = float(
        db.query(func.coalesce(func.sum(ConversaoVenda.valor_venda), 0.0))
        .filter(ConversaoVenda.campanha_id.in_(ids_ativos))
        .filter(ConversaoVenda.data_venda >= data_inicio)
        .scalar()
        or 0.0
    )

    leads_row = (
        db.query(
            func.coalesce(func.sum(MetricasDiarias.conversoes), 0),
        )
        .filter(MetricasDiarias.campanha_id.in_(ids_ativos))
        .filter(MetricasDiarias.data >= data_inicio.date())
        .first()
    )
    total_leads = int((leads_row[0] if leads_row else 0) or 0)
    roas_geral = (receita_total / gasto_total) if gasto_total > 0 else None
    breakdown_servicos = (
        _calcular_breakdown_servicos(db=db, ids_campanhas=ids_ativos, data_inicio=data_inicio)
        if incluir_servicos
        else None
    )

    return PerformanceConsolidadaResponse(
        gasto_total=gasto_total,
        receita_total=receita_total,
        roas_geral=roas_geral,
        total_leads=total_leads,
        breakdown_servicos=breakdown_servicos,
    )


@client_router.get("/performance-consolidada", response_model=PerformanceConsolidadaResponse)
def performance_consolidada_cliente(
    campanha_id: Optional[int] = Query(default=None),
    incluir_servicos: bool = Query(default=False),
    periodo_dias: int = Query(default=7, ge=1, le=365),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.cliente_id:
        raise HTTPException(status_code=403, detail="Usuario sem cliente vinculado.")
    return performance_consolidada(
        cliente_id=current_user.cliente_id,
        campanha_id=campanha_id,
        incluir_servicos=incluir_servicos,
        periodo_dias=periodo_dias,
        db=db,
    )


@client_router.get("/campanhas", response_model=list[CampanhaResponse])
def listar_campanhas_cliente(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.cliente_id:
        raise HTTPException(status_code=403, detail="Usuario sem cliente vinculado.")
    return listar_campanhas(cliente_id=current_user.cliente_id, db=db)


@router.post("/registrar-venda")
def registrar_venda(payload: RegistrarVendaRequest, db: Session = Depends(get_db)):
    campanha = db.query(Campanha).filter(Campanha.id == payload.campanha_id).first()
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada para registro de venda.")

    venda = ConversaoVenda(
        campanha_id=payload.campanha_id,
        valor_venda=float(payload.valor),
        canal=(payload.canal or "WHATSAPP").strip().upper(),
    )
    db.add(venda)
    db.commit()
    db.refresh(venda)

    return {
        "status": "sucesso",
        "mensagem": "Venda registrada com sucesso.",
        "venda_id": venda.id,
        "campanha_id": venda.campanha_id,
        "valor_venda": venda.valor_venda,
        "canal": venda.canal,
        "data_venda": venda.data_venda,
    }


@router.post("/otimizar-servico")
def otimizar_servico(
    payload: OtimizarServicoRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campanha = db.query(Campanha).filter(Campanha.id == payload.campanha_id).first()
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")
    if not campanha.plataforma_campanha_id:
        raise HTTPException(status_code=400, detail="Campanha sem ID de plataforma para otimizacao.")

    config = db.query(FerrioliConfig).first()
    if not config:
        raise HTTPException(status_code=500, detail="Configuracao master nao encontrada.")

    acao = (payload.acao or "").strip().upper()
    if acao not in {"PAUSAR", "ESCALAR"}:
        raise HTTPException(status_code=400, detail="Acao invalida. Use PAUSAR ou ESCALAR.")
    if not (payload.nome_servico or "").strip():
        raise HTTPException(status_code=400, detail="nome_servico obrigatorio.")

    plataforma = (campanha.plataforma or "").upper()
    nome_servico = payload.nome_servico.strip()
    detalhes_log: dict[str, Any] = {
        "plataforma": plataforma,
        "campanha_id": campanha.id,
        "campanha_plataforma_id": campanha.plataforma_campanha_id,
        "nome_servico": nome_servico,
        "acao": acao,
    }

    if plataforma == "GOOGLE":
        cliente = db.query(Cliente).filter(Cliente.id == campanha.cliente_id).first()
        if not cliente or not cliente.google_customer_id:
            raise HTTPException(status_code=400, detail="Cliente sem google_customer_id para acao no Google Ads.")

        launcher = GoogleAdsLauncher()
        google_credentials = _montar_google_credentials(config)
        servico_info = launcher.localizar_adgroup_por_nome(
            customer_id=cliente.google_customer_id,
            plataforma_campanha_id=campanha.plataforma_campanha_id,
            nome_servico=nome_servico,
            credentials_dict=google_credentials,
        )
        if not servico_info:
            raise HTTPException(status_code=404, detail="Nao foi possivel localizar o AdGroup para este servico.")

        detalhes_log["service_id"] = servico_info["ad_group_id"]
        detalhes_log["service_name"] = servico_info["ad_group_name"]

        if acao == "PAUSAR":
            valor_anterior = servico_info.get("status_atual")
            sucesso = asyncio.run(
                launcher.atualizar_status_adgroup(
                    customer_id=cliente.google_customer_id,
                    ad_group_id=servico_info["ad_group_id"],
                    status="PAUSED",
                    credentials_dict=google_credentials,
                )
            )
            if not sucesso:
                raise HTTPException(status_code=502, detail="Falha ao pausar servico no Google Ads.")
            detalhes_log["valor_anterior"] = valor_anterior
            detalhes_log["valor_novo"] = "PAUSED"
        else:
            if payload.valor is None or float(payload.valor) <= 0:
                raise HTTPException(status_code=400, detail="Informe um valor valido para ESCALAR.")
            valor_anterior = launcher.obter_orcamento_campanha(
                customer_id=cliente.google_customer_id,
                plataforma_campanha_id=campanha.plataforma_campanha_id,
                credentials_dict=google_credentials,
            )
            sucesso = asyncio.run(
                launcher.atualizar_orcamento_campanha(
                    customer_id=cliente.google_customer_id,
                    campaign_id=campanha.plataforma_campanha_id,
                    novo_valor=float(payload.valor),
                    credentials_dict=google_credentials,
                )
            )
            if not sucesso:
                raise HTTPException(status_code=502, detail="Falha ao atualizar orcamento no Google Ads.")
            detalhes_log["valor_anterior"] = valor_anterior
            detalhes_log["valor_novo"] = float(payload.valor)

    elif plataforma == "META":
        launcher = MetaAdsLauncher()
        meta_credentials = _montar_meta_credentials(config)
        servico_info = launcher.localizar_adset_por_nome(
            plataforma_campanha_id=campanha.plataforma_campanha_id,
            nome_servico=nome_servico,
            credentials_dict=meta_credentials,
        )
        if not servico_info:
            raise HTTPException(status_code=404, detail="Nao foi possivel localizar o AdSet para este servico.")

        detalhes_log["service_id"] = servico_info["adset_id"]
        detalhes_log["service_name"] = servico_info["adset_name"]

        if acao == "PAUSAR":
            valor_anterior = servico_info.get("status_atual")
            sucesso = asyncio.run(
                launcher.atualizar_status_adset(
                    adset_id=servico_info["adset_id"],
                    status="PAUSED",
                    credentials_dict=meta_credentials,
                )
            )
            if not sucesso:
                raise HTTPException(status_code=502, detail="Falha ao pausar servico na Meta.")
            detalhes_log["valor_anterior"] = valor_anterior
            detalhes_log["valor_novo"] = "PAUSED"
        else:
            if payload.valor is None or float(payload.valor) <= 0:
                raise HTTPException(status_code=400, detail="Informe um valor valido para ESCALAR.")
            valor_anterior = servico_info.get("daily_budget")
            sucesso = asyncio.run(
                launcher.atualizar_orcamento_adset(
                    adset_id=servico_info["adset_id"],
                    novo_valor=float(payload.valor),
                    credentials_dict=meta_credentials,
                )
            )
            if not sucesso:
                raise HTTPException(status_code=502, detail="Falha ao atualizar orcamento do servico na Meta.")
            detalhes_log["valor_anterior"] = valor_anterior
            detalhes_log["valor_novo"] = float(payload.valor)
    else:
        raise HTTPException(status_code=400, detail="Plataforma da campanha nao suportada para otimizacao.")

    try:
        registrar_log_safe(
            db=db,
            user_id=current_user.id,
            acao="OTIMIZAR_SERVICO",
            recurso=f"Campanha #{campanha.id} - {nome_servico}",
            detalhes=detalhes_log,
            request=request,
        )
    except Exception:
        pass

    return {
        "status": "sucesso",
        "mensagem": "Acao de otimizacao executada com sucesso.",
        "resultado": detalhes_log,
    }


def _obter_contexto_google_para_campanha(campanha_id: int, db: Session) -> tuple[Campanha, Cliente, FerrioliConfig]:
    campanha = db.query(Campanha).filter(Campanha.id == campanha_id).first()
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")
    if (campanha.plataforma or "").upper() != "GOOGLE":
        raise HTTPException(status_code=400, detail="Funcionalidade disponivel apenas para campanhas GOOGLE.")
    if not campanha.plataforma_campanha_id:
        raise HTTPException(status_code=400, detail="Campanha sem plataforma_campanha_id.")

    cliente = db.query(Cliente).filter(Cliente.id == campanha.cliente_id).first()
    if not cliente or not cliente.google_customer_id:
        raise HTTPException(status_code=400, detail="Cliente sem google_customer_id para consulta de termos.")

    config = db.query(FerrioliConfig).first()
    if not config:
        raise HTTPException(status_code=500, detail="Configuracao master nao encontrada.")
    return campanha, cliente, config


@router.get("/dispositivos/performance")
def listar_performance_dispositivos(
    campanha_id: int = Query(...),
    periodo_dias: int = Query(default=15, ge=1, le=90),
    db: Session = Depends(get_db),
):
    campanha, cliente, config = _obter_contexto_google_para_campanha(campanha_id=campanha_id, db=db)
    dispositivos = GoogleMetricsCollector().fetch_device_performance(
        customer_id=cliente.google_customer_id,
        campaign_id=campanha.plataforma_campanha_id,
        periodo_dias=periodo_dias,
        credentials_dict=_montar_google_credentials(config),
    )
    analise = asyncio.run(
        analisar_performance_dispositivos(
            dados_dispositivos=dispositivos,
            openai_api_key=config.openai_api_key,
        )
    )
    sugestoes = []
    for item in (analise.get("sugestoes") or []):
        sugestoes.append(
            {
                "dispositivo": str(item.get("dispositivo", "")).upper(),
                "ajuste_percentual": float(item.get("ajuste_percentual", 0.0) or 0.0),
                "justificativa": str(item.get("justificativa", "")).strip(),
                "severidade": str(item.get("severidade", "MEDIA")).upper(),
            }
        )
    return {
        "status": "sucesso",
        "campanha_id": campanha.id,
        "periodo_dias": periodo_dias,
        "media_cpa": analise.get("media_cpa"),
        "dispositivos": analise.get("dispositivos", dispositivos),
        "sugestoes": sugestoes,
        "resumo_ia": analise.get("resumo_ia", ""),
    }


@router.post("/dispositivos/ajustar")
def ajustar_dispositivo(
    payload: AjustarDispositivoRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campanha, cliente, config = _obter_contexto_google_para_campanha(campanha_id=payload.campanha_id, db=db)
    launcher = GoogleAdsLauncher()
    resultado = asyncio.run(
        launcher.ajustar_lance_dispositivo(
            customer_id=cliente.google_customer_id,
            campaign_id=campanha.plataforma_campanha_id,
            dispositivo=payload.dispositivo,
            ajuste_percentual=float(payload.ajuste_percentual),
            credentials_dict=_montar_google_credentials(config),
        )
    )
    if not resultado.get("sucesso"):
        raise HTTPException(status_code=502, detail=resultado.get("erro") or "Falha ao ajustar lance por dispositivo.")

    try:
        registrar_log_safe(
            db=db,
            user_id=current_user.id,
            acao="AJUSTE_DISPOSITIVO",
            recurso=f"Campanha #{campanha.id} - {str(payload.dispositivo).upper()}",
            detalhes={
                "campanha_id": campanha.id,
                "campanha_plataforma_id": campanha.plataforma_campanha_id,
                "dispositivo": str(payload.dispositivo).upper(),
                "ajuste_percentual": float(payload.ajuste_percentual),
                "bid_modifier_anterior": resultado.get("bid_modifier_anterior"),
                "bid_modifier_novo": resultado.get("bid_modifier_novo"),
            },
            request=request,
        )
    except Exception:
        pass

    return {
        "status": "sucesso",
        "mensagem": "Ajuste de dispositivo aplicado com sucesso.",
        "resultado": resultado,
    }


@router.get("/horarios/performance")
def listar_performance_horarios(
    campanha_id: int = Query(...),
    periodo_dias: int = Query(default=15, ge=1, le=90),
    db: Session = Depends(get_db),
):
    campanha, cliente, config = _obter_contexto_google_para_campanha(campanha_id=campanha_id, db=db)
    horarios = GoogleMetricsCollector().fetch_hourly_performance(
        customer_id=cliente.google_customer_id,
        campaign_id=campanha.plataforma_campanha_id,
        periodo_dias=periodo_dias,
        credentials_dict=_montar_google_credentials(config),
    )
    analise = asyncio.run(
        analisar_performance_horarios(
            dados_horarios=horarios,
            openai_api_key=config.openai_api_key,
        )
    )
    sugestoes = []
    for item in (analise.get("sugestoes") or []):
        sugestoes.append(
            {
                "dia_semana": str(item.get("dia_semana", "UNSPECIFIED")).upper(),
                "hora_inicio": int(item.get("hora_inicio", 0) or 0),
                "hora_fim": int(item.get("hora_fim", 1) or 1),
                "ajuste_percentual": float(item.get("ajuste_percentual", 0.0) or 0.0),
                "justificativa": str(item.get("justificativa", "")).strip(),
                "severidade": str(item.get("severidade", "MEDIA")).upper(),
            }
        )
    return {
        "status": "sucesso",
        "campanha_id": campanha.id,
        "periodo_dias": periodo_dias,
        "media_cpa": analise.get("media_cpa"),
        "horarios": analise.get("horarios", horarios),
        "sugestoes": sugestoes,
        "resumo_ia": analise.get("resumo_ia", ""),
    }


@router.post("/horarios/ajustar")
def ajustar_horario(
    payload: AjustarHorarioRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campanha, cliente, config = _obter_contexto_google_para_campanha(campanha_id=payload.campanha_id, db=db)
    launcher = GoogleAdsLauncher()
    resultado = asyncio.run(
        launcher.ajustar_programacao_horario(
            customer_id=cliente.google_customer_id,
            campaign_id=campanha.plataforma_campanha_id,
            dia_semana=payload.dia_semana,
            hora_inicio=payload.hora_inicio,
            hora_fim=payload.hora_fim,
            ajuste_percentual=float(payload.ajuste_percentual),
            credentials_dict=_montar_google_credentials(config),
        )
    )
    if not resultado.get("sucesso"):
        raise HTTPException(status_code=502, detail=resultado.get("erro") or "Falha ao ajustar horario.")
    try:
        registrar_log_safe(
            db=db,
            user_id=current_user.id,
            acao="AJUSTE_HORARIO",
            recurso=(
                f"Campanha #{campanha.id} - "
                f"{str(payload.dia_semana).upper()} {int(payload.hora_inicio):02d}h-{int(payload.hora_fim):02d}h"
            ),
            detalhes={
                "campanha_id": campanha.id,
                "campanha_plataforma_id": campanha.plataforma_campanha_id,
                "dia_semana": str(payload.dia_semana).upper(),
                "hora_inicio": int(payload.hora_inicio),
                "hora_fim": int(payload.hora_fim),
                "ajuste_percentual": float(payload.ajuste_percentual),
                "bid_modifier_anterior": resultado.get("bid_modifier_anterior"),
                "bid_modifier_novo": resultado.get("bid_modifier_novo"),
            },
            request=request,
        )
    except Exception:
        pass
    return {
        "status": "sucesso",
        "mensagem": "Ajuste de horario aplicado com sucesso.",
        "resultado": resultado,
    }


@router.get("/termos-busca")
def listar_termos_busca(
    campanha_id: int = Query(...),
    periodo_dias: int = Query(default=7, ge=1, le=90),
    nome_servico: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    campanha, cliente, config = _obter_contexto_google_para_campanha(campanha_id=campanha_id, db=db)
    ctr_alto_threshold = 3.0
    termos = GoogleMetricsCollector().fetch_search_terms(
        customer_id=cliente.google_customer_id,
        campaign_id=campanha.plataforma_campanha_id,
        periodo_dias=periodo_dias,
        credentials_dict=_montar_google_credentials(config),
    )
    if nome_servico:
        nome_alvo = nome_servico.strip().lower()
        termos = [item for item in termos if nome_alvo in str(item.get("nome_servico", "")).lower()]

    custo_total = 0.0
    custo_com_conversao = 0.0
    custo_termos_sugeridos = 0.0
    desperdicio_total_periodo = 0.0
    for item in termos:
        cost = float(item.get("cost", 0.0) or 0.0)
        conversions = int(item.get("conversions", 0) or 0)
        ctr = float(item.get("ctr", 0.0) or 0.0)
        sugestao_regra = conversions == 0 and ctr >= ctr_alto_threshold
        item["sugerido_negativar"] = sugestao_regra

        custo_total += cost
        if conversions > 0:
            custo_com_conversao += cost
        if sugestao_regra:
            custo_termos_sugeridos += cost
            desperdicio_total_periodo += cost

    economia_potencial_mensal = (custo_termos_sugeridos / float(max(1, periodo_dias))) * 30.0
    indice_pureza_trafego = (custo_com_conversao / custo_total * 100.0) if custo_total > 0 else 0.0

    termos_30_dias = GoogleMetricsCollector().fetch_search_terms(
        customer_id=cliente.google_customer_id,
        campaign_id=campanha.plataforma_campanha_id,
        periodo_dias=30,
        credentials_dict=_montar_google_credentials(config),
    )
    if nome_servico:
        nome_alvo = nome_servico.strip().lower()
        termos_30_dias = [
            item for item in termos_30_dias if nome_alvo in str(item.get("nome_servico", "")).lower()
        ]
    desperdicio_por_data: dict[str, float] = {}
    for item in termos_30_dias:
        data = str(item.get("date") or "")
        if not data:
            continue
        conversions = int(item.get("conversions", 0) or 0)
        ctr = float(item.get("ctr", 0.0) or 0.0)
        if conversions == 0 and ctr >= ctr_alto_threshold:
            desperdicio_por_data[data] = float(desperdicio_por_data.get(data, 0.0) + float(item.get("cost", 0.0) or 0.0))
    tendencia_desperdicio_30_dias = [
        {"data": data, "custo": round(float(custo), 2)}
        for data, custo in sorted(desperdicio_por_data.items(), key=lambda item: item[0])
    ]

    return {
        "status": "sucesso",
        "campanha_id": campanha.id,
        "periodo_dias": periodo_dias,
        "total_termos": len(termos),
        "desperdicio_identificado_periodo": round(custo_termos_sugeridos, 2),
        "desperdicio_total_periodo": round(desperdicio_total_periodo, 2),
        "economia_potencial_mensal": round(economia_potencial_mensal, 2),
        "indice_pureza_trafego": round(indice_pureza_trafego, 2),
        "tendencia_desperdicio_30_dias": tendencia_desperdicio_30_dias,
        "termos": termos,
    }


@router.post("/termos-busca/analisar")
def analisar_termos_busca(
    payload: AnalisarTermosRequest,
    db: Session = Depends(get_db),
):
    campanha, cliente, config = _obter_contexto_google_para_campanha(campanha_id=payload.campanha_id, db=db)
    termos = GoogleMetricsCollector().fetch_search_terms(
        customer_id=cliente.google_customer_id,
        campaign_id=campanha.plataforma_campanha_id,
        periodo_dias=payload.periodo_dias,
        credentials_dict=_montar_google_credentials(config),
    )

    nome_alvo = payload.nome_servico.strip().lower()
    termos_filtrados = [
        item
        for item in termos
        if nome_alvo in str(item.get("nome_servico", "")).lower()
        and (not payload.ad_group_id or str(item.get("ad_group_id", "")) == str(payload.ad_group_id))
    ]
    termos_para_ia = [
        {
            "search_term": item.get("search_term"),
            "clicks": item.get("clicks"),
            "cost": item.get("cost"),
            "conversions": item.get("conversions"),
        }
        for item in termos_filtrados
    ]
    analise = asyncio.run(
        analisar_termos_sujos(
            termos_lista=termos_para_ia,
            nome_servico=payload.nome_servico,
            openai_api_key=config.openai_api_key,
        )
    )
    sugestoes = [str(item).strip() for item in (analise.get("termos_negativar") or []) if str(item).strip()]
    sugestoes_norm = {item.lower() for item in sugestoes}
    termos_enriquecidos = []
    for item in termos_filtrados:
        termo = str(item.get("search_term", "")).strip()
        item_enriquecido = dict(item)
        item_enriquecido["sugerido_negativar"] = termo.lower() in sugestoes_norm
        termos_enriquecidos.append(item_enriquecido)

    return {
        "status": "sucesso",
        "campanha_id": campanha.id,
        "nome_servico": payload.nome_servico,
        "ad_group_id": (payload.ad_group_id or None),
        "termos_negativar": sugestoes,
        "termos": termos_enriquecidos,
    }


@router.post("/termos-busca/negativar")
def negativar_termos_busca(
    payload: NegativarTermosRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campanha, cliente, config = _obter_contexto_google_para_campanha(campanha_id=payload.campanha_id, db=db)
    termos = [str(item or "").strip() for item in (payload.termos or []) if str(item or "").strip()]
    if not termos:
        raise HTTPException(status_code=400, detail="Lista de termos vazia para negativacao.")
    periodo_ref = max(1, int(payload.periodo_dias or 30))
    termos_metricas = GoogleMetricsCollector().fetch_search_terms(
        customer_id=cliente.google_customer_id,
        campaign_id=campanha.plataforma_campanha_id,
        periodo_dias=periodo_ref,
        credentials_dict=_montar_google_credentials(config),
    )
    nome_alvo = payload.nome_servico.strip().lower()
    custo_por_termo: dict[str, float] = {}
    for item in termos_metricas:
        if str(item.get("ad_group_id", "")) != str(payload.ad_group_id):
            continue
        if nome_alvo not in str(item.get("nome_servico", "")).lower():
            continue
        termo_key = str(item.get("search_term", "")).strip().lower()
        if not termo_key:
            continue
        custo_por_termo[termo_key] = float(custo_por_termo.get(termo_key, 0.0) + float(item.get("cost", 0.0) or 0.0))

    launcher = GoogleAdsLauncher()
    resultado = asyncio.run(
        launcher.negativar_termos_adgroup(
            customer_id=cliente.google_customer_id,
            ad_group_id=payload.ad_group_id,
            lista_termos=termos,
            credentials_dict=_montar_google_credentials(config),
        )
    )
    if not resultado.get("sucesso"):
        raise HTTPException(status_code=502, detail="Falha ao negativar termos no Google Ads.")

    for termo in resultado.get("negativados", []):
        try:
            registrar_log_safe(
                db=db,
                user_id=current_user.id,
                acao="NEGATIVAR_TERMO",
                recurso=f"Campanha #{campanha.id} - {payload.nome_servico}",
                detalhes={
                    "campanha_id": campanha.id,
                    "campanha_plataforma_id": campanha.plataforma_campanha_id,
                    "ad_group_id": payload.ad_group_id,
                    "nome_servico": payload.nome_servico,
                    "termo_negativado": termo,
                    "periodo_dias_ref": periodo_ref,
                    "custo_periodo_termo": round(float(custo_por_termo.get(str(termo).lower(), 0.0)), 4),
                    "economia_mensal_estimada": round(
                        (float(custo_por_termo.get(str(termo).lower(), 0.0)) / float(periodo_ref)) * 30.0,
                        4,
                    ),
                },
                request=request,
            )
        except Exception:
            pass

    return {
        "status": "sucesso",
        "mensagem": "Termos negativados com sucesso.",
        "resultado": resultado,
    }


def _formatar_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _gerar_pdf_relatorio_campanha(
    campanha: Campanha,
    cliente: Cliente,
    gasto: float,
    faturamento: float,
    roas: Optional[float],
    total_leads: int,
    economia_ia: float,
) -> Path:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise RuntimeError(
            "Dependencia reportlab nao disponivel. Instale com `pip install reportlab`."
        ) from exc

    temp = NamedTemporaryFile(prefix=f"relatorio_campanha_{campanha.id}_", suffix=".pdf", delete=False)
    temp_path = Path(temp.name)
    temp.close()

    c = canvas.Canvas(str(temp_path), pagesize=A4)
    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, f"Relatorio de Performance - Campanha #{campanha.id}")
    y -= 28

    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Cliente: {cliente.nome}")
    y -= 18
    c.drawString(40, y, f"Plataforma: {campanha.plataforma}")
    y -= 18
    c.drawString(40, y, f"Status: {campanha.status}")
    y -= 24

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "KPI Consolidado")
    y -= 18
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Investimento: {_formatar_brl(gasto)}")
    y -= 18
    c.drawString(40, y, f"Faturamento: {_formatar_brl(faturamento)}")
    y -= 18
    c.drawString(40, y, f"ROAS: {(f'{roas:.2f}x' if roas is not None else 'N/A')}")
    y -= 24
    c.drawString(40, y, f"Total de Leads: {total_leads}")
    y -= 24
    c.setFont("Helvetica-Bold", 11)
    c.setFillColorRGB(0.1, 0.6, 0.2)
    c.drawString(40, y, f"Economia com IA (Termos Sujos): {_formatar_brl(economia_ia)}")
    c.setFillColorRGB(0, 0, 0)
    y -= 24

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(40, y, f"Gerado em: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    c.save()
    return temp_path


@router.post("/enviar-relatorio-whatsapp/{campanha_id}")
def enviar_relatorio_whatsapp(
    campanha_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campanha = db.query(Campanha).filter(Campanha.id == campanha_id).first()
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")

    cliente = db.query(Cliente).filter(Cliente.id == campanha.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente da campanha nao encontrado.")
    if not cliente.whatsapp_group_jid:
        raise HTTPException(status_code=400, detail="Cliente sem whatsapp_group_jid configurado.")

    config = db.query(FerrioliConfig).first()
    if not config:
        raise HTTPException(status_code=500, detail="Configuracoes globais nao encontradas.")

    gasto = float(
        db.query(func.coalesce(func.sum(MetricasDiarias.spend), 0.0))
        .filter(MetricasDiarias.campanha_id == campanha.id)
        .scalar()
        or 0.0
    )
    faturamento = float(
        db.query(func.coalesce(func.sum(ConversaoVenda.valor_venda), 0.0))
        .filter(ConversaoVenda.campanha_id == campanha.id)
        .scalar()
        or 0.0
    )
    roas = (faturamento / gasto) if gasto > 0 else None
    total_leads = int(
        db.query(func.coalesce(func.sum(MetricasDiarias.conversoes), 0))
        .filter(MetricasDiarias.campanha_id == campanha.id)
        .scalar()
        or 0
    )
    data_inicio_logs = datetime.utcnow() - timedelta(days=30)
    logs_negativacao = (
        db.query(AuditLog)
        .filter(
            AuditLog.acao == "NEGATIVAR_TERMO",
            AuditLog.timestamp >= data_inicio_logs,
        )
        .all()
    )
    economia_ia = sum(
        float((log.detalhes or {}).get("economia_mensal_estimada", 0.0) or 0.0)
        for log in logs_negativacao
        if int(((log.detalhes or {}).get("campanha_id", 0) or 0)) == campanha.id
    )

    insight_estrategico: Optional[str] = None
    try:
        dados_performance = montar_dados_performance_reais_por_servico(
            db=db,
            campanha_id=campanha.id,
            cliente_nome=cliente.nome,
        )
        insight_estrategico = asyncio.run(
            gerar_insight_estrategico(
                dados_performance=dados_performance,
                openai_api_key=config.openai_api_key,
            )
        )
    except Exception:
        logger.exception("Falha ao gerar insight estrategico da IA para campanha_id=%s", campanha.id)
        insight_estrategico = None

    mensagem = (
        "📊 *Relatorio de Performance*\n"
        f"Campanha #{campanha.id} - {cliente.nome}\n\n"
        f"💸 Investimento: {_formatar_brl(gasto)}\n"
        f"💰 Faturamento: {_formatar_brl(faturamento)}\n"
        f"📈 ROAS: {(f'{roas:.2f}x' if roas is not None else 'N/A')}"
    )
    mensagem += f"\n👥 Leads Gerados: {total_leads}"
    if economia_ia > 0:
        mensagem += f"\n🛡️ Economia com IA: {_formatar_brl(economia_ia)} salvos!"
    if insight_estrategico:
        mensagem += f"\n\n💡 *Insight Estrategico (IA):*\n{insight_estrategico}"

    pdf_path: Optional[Path] = None
    try:
        pdf_path = _gerar_pdf_relatorio_campanha(
            campanha=campanha,
            cliente=cliente,
            gasto=gasto,
            faturamento=faturamento,
            roas=roas,
            total_leads=total_leads,
            economia_ia=economia_ia,
        )
        pdf_nome = f"relatorio_campanha_{campanha.id}.pdf"
        result = EvolutionService().enviar_relatorio_pdf(
            config=config,
            remote_jid=cliente.whatsapp_group_jid,
            mensagem=mensagem,
            pdf_path=str(pdf_path),
            pdf_nome=pdf_nome,
        )
        try:
            registrar_log_safe(
                db=db,
                user_id=current_user.id,
                acao="ENVIO_WHATSAPP",
                recurso=f"Campanha #{campanha.id}",
                detalhes={
                    "cliente_id": cliente.id,
                    "remote_jid": cliente.whatsapp_group_jid,
                    "tipo": "RELATORIO_PERFORMANCE",
                    "insight_ia": insight_estrategico,
                    "insight_status": ("gerado" if insight_estrategico else "nao_gerado"),
                },
                request=request,
            )
        except Exception:
            pass
        return {
            "status": "sucesso",
            "mensagem": "Relatorio enviado com sucesso para o grupo de WhatsApp.",
            "campanha_id": campanha.id,
            "cliente_id": cliente.id,
            "remote_jid": cliente.whatsapp_group_jid,
            "evolution": result,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao enviar relatorio via Evolution: {exc}") from exc
    finally:
        if pdf_path and pdf_path.exists():
            pdf_path.unlink(missing_ok=True)


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


@router.get("/logs-atividade", response_model=list[AuditLogResponse])
def listar_logs_atividade(
    acao: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog).options(joinedload(AuditLog.usuario)).order_by(AuditLog.timestamp.desc())
    if acao:
        query = query.filter(AuditLog.acao == acao.strip().upper())
    logs = query.limit(200).all()
    return [
        AuditLogResponse(
            id=log.id,
            timestamp=log.timestamp,
            user_id=log.user_id,
            usuario_email=(log.usuario.email if log.usuario else None),
            acao=log.acao,
            recurso=log.recurso,
            detalhes=log.detalhes,
            ip_address=log.ip_address,
        )
        for log in logs
    ]


@router.get("/stats-ia")
def stats_ia(
    periodo_dias: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    data_inicio = datetime.utcnow() - timedelta(days=max(1, int(periodo_dias)))
    rows = (
        db.query(
            ConsumoIA.modelo,
            func.coalesce(func.sum(ConsumoIA.tokens_input), 0).label("tokens_input"),
            func.coalesce(func.sum(ConsumoIA.tokens_output), 0).label("tokens_output"),
            func.coalesce(func.sum(ConsumoIA.custo_estimado), 0.0).label("custo_estimado"),
        )
        .filter(ConsumoIA.timestamp >= data_inicio)
        .group_by(ConsumoIA.modelo)
        .all()
    )

    por_modelo = []
    custo_total = 0.0
    tokens_total = 0
    for row in rows:
        tokens_in = int(row.tokens_input or 0)
        tokens_out = int(row.tokens_output or 0)
        custo = float(row.custo_estimado or 0.0)
        por_modelo.append(
            {
                "modelo": str(row.modelo),
                "tokens_input": tokens_in,
                "tokens_output": tokens_out,
                "tokens_total": tokens_in + tokens_out,
                "custo_estimado": round(custo, 6),
            }
        )
        custo_total += custo
        tokens_total += tokens_in + tokens_out

    logs_negativacao = (
        db.query(AuditLog)
        .filter(
            AuditLog.acao == "NEGATIVAR_TERMO",
            AuditLog.timestamp >= data_inicio,
        )
        .all()
    )
    economia_ia = 0.0
    for log in logs_negativacao:
        detalhes = log.detalhes or {}
        economia_ia += float(detalhes.get("economia_mensal_estimada", 0.0) or 0.0)

    roi_estimado_limpeza = float(economia_ia - custo_total)

    return {
        "status": "sucesso",
        "periodo_dias": periodo_dias,
        "custo_total_ia": round(float(custo_total), 6),
        "tokens_total": int(tokens_total),
        "economia_gerada_ia": round(float(economia_ia), 4),
        "roi_estimado_limpeza": round(float(roi_estimado_limpeza), 4),
        "por_modelo": por_modelo,
    }


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

    _aplicar_campos_campanha_update(campanha, payload)

    db.commit()
    db.refresh(campanha)

    campanha = (
        db.query(Campanha)
        .options(joinedload(Campanha.cliente), selectinload(Campanha.landing_pages))
        .filter(Campanha.id == campanha_id)
        .first()
    )
    return _serializar_campanha(campanha)


def _aplicar_campos_campanha_update(campanha: Campanha, payload: CampanhaUpdateRequest) -> None:
    """Aplica apenas campos enviados no payload, com sanitizacao de strings."""
    update_data = payload.model_dump(exclude_unset=True)
    if payload.meta_pixel_id is not None:
        update_data["meta_pixel_id"] = payload.meta_pixel_id.strip()
    if payload.google_conversion_action_id is not None:
        update_data["google_conversion_action_id"] = payload.google_conversion_action_id.strip()
    if payload.endereco_negocio is not None:
        update_data["endereco_negocio"] = payload.endereco_negocio.strip()

    for field_name, field_value in update_data.items():
        setattr(campanha, field_name, field_value)


@router.post("/campanhas/{campanha_id}/aprovar", response_model=CampanhaAprovacaoResponse)
def aprovar_campanha_rascunho(
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

    if campanha.status != "RASCUNHO":
        raise HTTPException(
            status_code=400,
            detail="Apenas campanhas em status RASCUNHO podem ser aprovadas por esta rota.",
        )

    _aplicar_campos_campanha_update(campanha, payload)
    campanha.status = "APROVADA"

    db.commit()
    db.refresh(campanha)

    campanha = (
        db.query(Campanha)
        .options(joinedload(Campanha.cliente), selectinload(Campanha.landing_pages))
        .filter(Campanha.id == campanha_id)
        .first()
    )
    return CampanhaAprovacaoResponse(
        mensagem="Campanha aprovada com sucesso. Pronta para publicacao no Launcher.",
        campanha=_serializar_campanha(campanha),
    )
