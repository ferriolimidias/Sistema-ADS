import logging
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from models.database import get_db
from models.schema import Campanha, MidiaCampanha

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload/{campanha_id}")
async def upload_midia(
    campanha_id: int,
    arquivo: UploadFile = File(...),
    nome_servico: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    campanha = db.query(Campanha).filter(Campanha.id == campanha_id).first()
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")

    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Arquivo invalido.")

    extensao = Path(arquivo.filename).suffix or ".bin"
    nome_arquivo = f"{uuid4().hex}{extensao}"
    diretorio_destino = Path("public/media")
    diretorio_destino.mkdir(parents=True, exist_ok=True)
    caminho_destino = diretorio_destino / nome_arquivo

    conteudo = await arquivo.read()
    caminho_destino.write_bytes(conteudo)

    registro = MidiaCampanha(
        campanha_id=campanha_id,
        nome_arquivo=nome_arquivo,
        caminho_arquivo=str(caminho_destino).replace("\\", "/"),
        mime_type=arquivo.content_type,
        nome_servico=(nome_servico.strip() if nome_servico else None),
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)

    logger.info(
        "Midia enviada com sucesso. campanha_id=%s midia_id=%s nome_servico=%s",
        campanha_id,
        registro.id,
        registro.nome_servico,
    )

    return {
        "status": "sucesso",
        "mensagem": "Midia enviada com sucesso.",
        "midia_id": registro.id,
        "campanha_id": campanha_id,
        "nome_servico": registro.nome_servico,
        "caminho_arquivo": registro.caminho_arquivo,
    }


@router.get("/{campanha_id}")
def listar_midias(
    campanha_id: int,
    nome_servico: Optional[str] = None,
    db: Session = Depends(get_db),
):
    campanha = db.query(Campanha).filter(Campanha.id == campanha_id).first()
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")

    query = db.query(MidiaCampanha).filter(MidiaCampanha.campanha_id == campanha_id)
    if nome_servico is not None:
        query = query.filter(MidiaCampanha.nome_servico == nome_servico.strip())

    midias = query.order_by(MidiaCampanha.id.desc()).all()
    return [
        {
            "id": midia.id,
            "campanha_id": midia.campanha_id,
            "nome_arquivo": midia.nome_arquivo,
            "caminho_arquivo": midia.caminho_arquivo,
            "mime_type": midia.mime_type,
            "nome_servico": midia.nome_servico,
            "data_criacao": midia.data_criacao,
        }
        for midia in midias
    ]
