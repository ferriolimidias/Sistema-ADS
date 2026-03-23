import asyncio
import logging
import re
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from engines.content_engine.generator import ContentGenerator
from engines.google_engine.launcher import GoogleAdsLauncher
from engines.meta_engine.launcher import MetaAdsLauncher
from engines.utils.security import require_admin_user
from models.database import get_db
from models.schema import Campanha, Cliente, FerrioliConfig, LandingPage, MidiaCampanha

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/builder", tags=["campaign-builder"], dependencies=[Depends(require_admin_user)])


class GerarAtivosRequest(BaseModel):
    cliente_id: int
    nome_servico: str
    detalhes_empresa: str
    plataforma: Optional[str] = "GOOGLE"


def _gerar_url_slug(nome_servico: str) -> str:
    slug_base = re.sub(r"[^a-z0-9]+", "-", nome_servico.lower()).strip("-")
    slug_base = slug_base or "landing-page"
    return f"{slug_base}-{uuid4().hex[:4]}"


def _salvar_html_em_arquivo(html: str, html_path: Path) -> None:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")


def _montar_google_credentials(ferrioli_config: FerrioliConfig) -> dict:
    return {
        "developer_token": ferrioli_config.google_mcc_token,
        "client_id": ferrioli_config.google_ads_client_id,
        "client_secret": ferrioli_config.google_ads_client_secret,
        "refresh_token": ferrioli_config.google_ads_refresh_token,
        "use_client_customer_id": ferrioli_config.google_ads_use_client_customer_id,
        "Maps_api_key": ferrioli_config.Maps_api_key,
    }


def _montar_configuracoes_banco(ferrioli_config: FerrioliConfig, cliente: Optional[Cliente] = None) -> dict:
    return {
        "meta_bm_token": ferrioli_config.meta_bm_token,
        "meta_access_token": ferrioli_config.meta_bm_token,
        "meta_ad_account_id": cliente.meta_ad_account_id if cliente else None,
        "meta_page_id": ferrioli_config.meta_page_id,
        "public_base_url": "https://seu-dominio.com",
        "google_mcc_token": ferrioli_config.google_mcc_token,
        "google_ads_client_id": ferrioli_config.google_ads_client_id,
        "google_ads_client_secret": ferrioli_config.google_ads_client_secret,
        "google_ads_refresh_token": ferrioli_config.google_ads_refresh_token,
        "google_ads_use_client_customer_id": ferrioli_config.google_ads_use_client_customer_id,
        "Maps_api_key": ferrioli_config.Maps_api_key,
    }


@router.post("/gerar-ativos")
async def gerar_ativos(request: GerarAtivosRequest, db: Session = Depends(get_db)):
    ferrioli_config = db.query(FerrioliConfig).first()
    if not ferrioli_config or not ferrioli_config.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY nao configurada em Ferrioli_Config.")

    cliente = db.query(Cliente).filter(Cliente.id == request.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")

    content_generator = ContentGenerator.from_ferrioli_config(ferrioli_config)
    plataforma = (request.plataforma or "GOOGLE").upper()
    if plataforma not in {"GOOGLE", "META"}:
        raise HTTPException(status_code=400, detail="Plataforma invalida. Use GOOGLE ou META.")

    copy_gerada = await content_generator.gerar_copy_campanha(
        nome_servico=request.nome_servico,
        detalhes_empresa=request.detalhes_empresa,
        plataforma=plataforma,
    )
    html_gerado = await content_generator.gerar_landing_page(
        nome_servico=request.nome_servico,
        copy_gerada=copy_gerada,
    )

    url_slug = _gerar_url_slug(request.nome_servico)
    html_path = Path("public/lps") / f"{url_slug}.html"
    await asyncio.to_thread(_salvar_html_em_arquivo, html_gerado, html_path)

    campanha = Campanha(
        cliente_id=cliente.id,
        id_plataforma=f"rascunho-{uuid4().hex[:8]}",
        plataforma=plataforma,
        tipo="SEARCH",
        status="RASCUNHO",
        orcamento_diario=0.0,
        roas_alvo=None,
        meta_pixel_id=None,
        google_conversion_action_id=None,
        copy_gerada=copy_gerada,
        assets_adicionais={
            "sitelinks": copy_gerada.get("sitelinks", []),
            "callouts": copy_gerada.get("callouts", []),
        },
    )
    db.add(campanha)
    db.flush()

    landing_page = LandingPage(
        campanha_id=campanha.id,
        url_slug=url_slug,
        html_path=str(html_path).replace("\\", "/"),
        status="RASCUNHO",
    )
    db.add(landing_page)
    db.commit()
    db.refresh(campanha)
    db.refresh(landing_page)

    logger.info(
        "Ativos gerados com sucesso. cliente_id=%s campanha_id=%s landing_page_id=%s",
        cliente.id,
        campanha.id,
        landing_page.id,
    )

    return {
        "status": "sucesso",
        "copies": copy_gerada,
        "landing_page_url": f"/lp/{url_slug}.html",
        "campanha_id": campanha.id,
        "landing_page_id": landing_page.id,
    }


@router.post("/aprovar/{campanha_id}")
async def aprovar_campanha(
    campanha_id: int,
    preview_mode: bool = False,
    x_preview_mode: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    header_preview = str(x_preview_mode or "").strip().lower() in {"1", "true", "yes", "on"}
    preview_mode = preview_mode or header_preview

    campanha = db.query(Campanha).filter(Campanha.id == campanha_id).first()
    if not campanha or campanha.status not in ("RASCUNHO", "APROVADA"):
        raise HTTPException(
            status_code=400,
            detail="Campanha nao encontrada ou nao esta em RASCUNHO/APROVADA (edite e aprove no dashboard antes de publicar).",
        )

    landing_page = db.query(LandingPage).filter(LandingPage.campanha_id == campanha.id).first()
    if not landing_page:
        raise HTTPException(status_code=400, detail="Landing page vinculada nao encontrada.")

    ferrioli_config = db.query(FerrioliConfig).first()
    if not ferrioli_config:
        raise HTTPException(status_code=500, detail="Configuracao master nao encontrada.")

    cliente = db.query(Cliente).filter(Cliente.id == campanha.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=400, detail="Cliente nao encontrado.")

    if not campanha.copy_gerada:
        raise HTTPException(status_code=400, detail="Campanha sem copy gerada para publicacao.")

    url_final = f"/lp/{landing_page.url_slug}.html"
    lista_midias = db.query(MidiaCampanha).filter(MidiaCampanha.campanha_id == campanha_id).all()
    configuracoes_banco = _montar_configuracoes_banco(ferrioli_config, cliente)
    configuracoes_banco["landing_page_url"] = url_final
    plataforma_campanha = (campanha.plataforma or "GOOGLE").upper()

    if preview_mode and plataforma_campanha != "META":
        raise HTTPException(
            status_code=400,
            detail="preview_mode atualmente suportado apenas para campanhas META.",
        )

    if plataforma_campanha == "META":
        if not configuracoes_banco.get("meta_page_id"):
            raise HTTPException(status_code=400, detail="meta_page_id nao configurado no banco de dados.")

        sucesso_criacao, plataforma_campanha_id, payload_preview = await MetaAdsLauncher().criar_campanha_meta(
            campanha=campanha,
            lista_midias=lista_midias,
            configuracoes=configuracoes_banco,
            preview_mode=preview_mode,
        )
        if preview_mode:
            if not sucesso_criacao:
                raise HTTPException(status_code=502, detail="Falha ao montar payload preview da META.")
            return {
                "status": "preview",
                "plataforma": "META",
                "campanha_id": campanha.id,
                "payload_preview": payload_preview,
                "mensagem": "Preview gerado com sucesso. Nenhuma publicacao foi realizada.",
            }
    else:
        if not cliente.google_customer_id:
            raise HTTPException(status_code=400, detail="google_customer_id nao encontrado para campanha GOOGLE.")

        google_credentials = _montar_google_credentials(ferrioli_config)
        if not all(
            [
                google_credentials["developer_token"],
                google_credentials["client_id"],
                google_credentials["client_secret"],
                google_credentials["refresh_token"],
            ]
        ):
            raise HTTPException(status_code=500, detail="Credenciais do Google Ads incompletas.")

        sucesso_criacao, plataforma_campanha_id = await GoogleAdsLauncher().criar_campanha_pesquisa(
            credentials_dict=google_credentials,
            customer_id=cliente.google_customer_id,
            orcamento_diario=campanha.orcamento_diario,
            url_final=url_final,
            copy_data=campanha.copy_gerada,
            campanha_id=campanha.id,
            public_base_url=str(configuracoes_banco.get("public_base_url") or "https://seu-dominio.com"),
            cpa_alvo=campanha.cpa_alvo,
            assets_adicionais=campanha.assets_adicionais,
            endereco_negocio=campanha.endereco_negocio,
            raio_geografico=campanha.raio_geografico,
            lista_midias=lista_midias,
        )

    if not sucesso_criacao or not plataforma_campanha_id:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao criar campanha na plataforma {plataforma_campanha}.",
        )

    campanha.plataforma_campanha_id = plataforma_campanha_id
    campanha.status = "ATIVA"
    landing_page.status = "ATIVA"
    db.commit()
    db.refresh(campanha)
    db.refresh(landing_page)

    logger.info(
        "Campanha aprovada com sucesso. campanha_id=%s plataforma_campanha_id=%s",
        campanha.id,
        campanha.plataforma_campanha_id,
    )

    return {
        "status": "sucesso",
        "mensagem": "Campanha aprovada e publicada com sucesso.",
        "campanha_id": campanha.id,
        "plataforma_campanha_id": campanha.plataforma_campanha_id,
        "landing_page_url": url_final,
    }
