import asyncio
import logging
import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from engines.content_engine.generator import ContentGenerator
from engines.google_engine.launcher import GoogleAdsLauncher
from models.database import get_db
from models.schema import Campanha, Cliente, FerrioliConfig, LandingPage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/builder", tags=["campaign-builder"])


class ConstruirCampanhaRequest(BaseModel):
    cliente_id: int
    nome_servico: str
    detalhes_empresa: str


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
    }


@router.post("/gerar-ativos")
async def gerar_ativos(request: ConstruirCampanhaRequest, db: Session = Depends(get_db)):
    ferrioli_config = db.query(FerrioliConfig).first()
    if not ferrioli_config or not ferrioli_config.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY nao configurada em Ferrioli_Config.")

    cliente = db.query(Cliente).filter(Cliente.id == request.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")

    content_generator = ContentGenerator.from_ferrioli_config(ferrioli_config)
    copy_gerada = await content_generator.gerar_copy_google_ads(
        nome_servico=request.nome_servico,
        detalhes_empresa=request.detalhes_empresa,
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
        plataforma="GOOGLE",
        tipo="SEARCH",
        status="RASCUNHO",
        orcamento_diario=0.0,
        roas_alvo=None,
        meta_pixel_id=None,
        google_conversion_action_id=None,
        copy_gerada=copy_gerada,
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
async def aprovar_campanha(campanha_id: int, db: Session = Depends(get_db)):
    campanha = db.query(Campanha).filter(Campanha.id == campanha_id).first()
    if not campanha or campanha.status != "RASCUNHO":
        raise HTTPException(status_code=400, detail="Campanha nao encontrada ou nao esta em status RASCUNHO.")

    landing_page = db.query(LandingPage).filter(LandingPage.campanha_id == campanha.id).first()
    if not landing_page:
        raise HTTPException(status_code=400, detail="Landing page vinculada nao encontrada.")

    ferrioli_config = db.query(FerrioliConfig).first()
    if not ferrioli_config:
        raise HTTPException(status_code=500, detail="Configuracao master nao encontrada.")

    cliente = db.query(Cliente).filter(Cliente.id == campanha.cliente_id).first()
    if not cliente or not cliente.google_customer_id:
        raise HTTPException(status_code=400, detail="Cliente ou google_customer_id nao encontrado.")

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
    if not campanha.copy_gerada:
        raise HTTPException(status_code=400, detail="Campanha sem copy gerada para publicacao.")

    url_final = f"/lp/{landing_page.url_slug}.html"

    plataforma_campanha_id = await GoogleAdsLauncher().criar_campanha_pesquisa(
        credentials_dict=google_credentials,
        customer_id=cliente.google_customer_id,
        orcamento_diario=campanha.orcamento_diario,
        url_final=url_final,
        copy_data=campanha.copy_gerada,
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
