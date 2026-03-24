import re
import unicodedata
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from models.database import get_db
from models.schema import Campanha, Cliente, MidiaCampanha

router = APIRouter(tags=["public"])


def _normalizar_nome_servico(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")
    return texto


def _montar_url_publica_midia(caminho_arquivo: str | None) -> str | None:
    if not caminho_arquivo:
        return None
    path = str(caminho_arquivo).replace("\\", "/")
    if path.startswith("public/"):
        return f"/{path}"
    return f"/public/{path.lstrip('/')}"


def _montar_whatsapp_link(numero_whatsapp: str | None, nome_servico: str, campanha_id: int) -> str | None:
    numero_limpo = re.sub(r"\D+", "", str(numero_whatsapp or ""))
    if not numero_limpo:
        return None

    mensagem = (
        f"Ola! Vi o anuncio sobre *{nome_servico}* e gostaria de mais informacoes. "
        f"[ID: {campanha_id}]"
    )
    return f"https://wa.me/{numero_limpo}?text={quote(mensagem)}"


def _montar_payload_landing(campanha: Campanha, cliente: Cliente | None, db: Session, nome_servico: str | None = None):
    copy_gerada = campanha.copy_gerada or {}
    grupos_google = copy_gerada.get("grupos_anuncios", []) or []
    conjuntos_meta = copy_gerada.get("conjuntos_anuncios", []) or []

    grupo_match = None
    conjunto_match = None
    alvo = _normalizar_nome_servico(nome_servico) if nome_servico else None

    if alvo:
        for item in grupos_google:
            if _normalizar_nome_servico(item.get("nome_servico", "")) == alvo:
                grupo_match = item
                break

        if not grupo_match:
            for item in conjuntos_meta:
                if _normalizar_nome_servico(item.get("nome_publico", "")) == alvo:
                    conjunto_match = item
                    break
    else:
        grupo_match = grupos_google[0] if grupos_google else None
        conjunto_match = conjuntos_meta[0] if conjuntos_meta else None

    if not grupo_match and not conjunto_match:
        raise HTTPException(status_code=404, detail="Servico nao encontrado na campanha.")

    midias = db.query(MidiaCampanha).filter(MidiaCampanha.campanha_id == campanha.id).all()
    midia_match = None
    if alvo:
        for midia in midias:
            if _normalizar_nome_servico(midia.nome_servico or "") == alvo:
                midia_match = midia
                break
    if not midia_match and midias:
        midia_match = midias[0]

    if grupo_match:
        titulo_oferta = (grupo_match.get("headlines") or [""])[0]
        texto_vendas = (grupo_match.get("descriptions") or [""])[0]
    else:
        titulo_oferta = (conjunto_match.get("titulo") or [""])[0]
        texto_vendas = (conjunto_match.get("texto_principal") or [""])[0]

    nome_servico_mensagem = (
        (grupo_match.get("nome_servico") if grupo_match else None)
        or (conjunto_match.get("nome_publico") if conjunto_match else None)
        or (nome_servico or "")
    )

    tema = None
    if isinstance(copy_gerada.get("tema"), dict):
        tema = copy_gerada.get("tema")
    elif isinstance(campanha.assets_adicionais, dict) and isinstance(campanha.assets_adicionais.get("tema"), dict):
        tema = campanha.assets_adicionais.get("tema")

    return {
        "cliente_id": campanha.cliente_id,
        "campanha_id": campanha.id,
        "copy_gerada": copy_gerada,
        "tema": tema,
        "nome_cliente": cliente.nome if cliente else "",
        "razao_social": cliente.razao_social if cliente else None,
        "cnpj": cliente.cnpj if cliente else None,
        "endereco_negocio": campanha.endereco_negocio,
        "titulo_oferta": str(titulo_oferta or "").strip(),
        "texto_vendas": str(texto_vendas or "").strip(),
        "url_imagem": _montar_url_publica_midia(midia_match.caminho_arquivo if midia_match else None),
        "whatsapp_link": _montar_whatsapp_link(
            numero_whatsapp=(cliente.whatsapp if cliente else None),
            nome_servico=str(nome_servico_mensagem or "Atendimento"),
            campanha_id=campanha.id,
        ),
    }


@router.get("/lp/{campanha_id}/{nome_servico}")
def obter_landing_data(campanha_id: int, nome_servico: str, db: Session = Depends(get_db)):
    campanha = db.query(Campanha).filter(Campanha.id == campanha_id).first()
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")
    cliente = campanha.cliente
    return _montar_payload_landing(campanha=campanha, cliente=cliente, db=db, nome_servico=nome_servico)


@router.get("/public/resolve-host")
def resolver_host_publico(host: str = Query(...), db: Session = Depends(get_db)):
    host_limpo = str(host or "").strip().lower()
    if not host_limpo:
        raise HTTPException(status_code=400, detail="Parametro host e obrigatorio.")

    cliente = db.query(Cliente).filter(Cliente.dominio_personalizado == host_limpo).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado para este host.")

    campanha = (
        db.query(Campanha)
        .filter(Campanha.cliente_id == cliente.id, Campanha.status == "ATIVA")
        .order_by(Campanha.id.desc())
        .first()
    )
    if not campanha:
        raise HTTPException(status_code=404, detail="Nenhuma campanha ativa encontrada para este cliente.")

    return _montar_payload_landing(campanha=campanha, cliente=cliente, db=db, nome_servico=None)
