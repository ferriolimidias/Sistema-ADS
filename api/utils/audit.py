import asyncio
from datetime import datetime, timedelta
import os
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from engines.utils.evolution_service import EvolutionService
from models.schema import AuditLog, ConfiguracaoSistema, FerrioliConfig, Usuario


def _extract_ip(request: Request | None) -> str | None:
    if not request:
        return None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


async def registrar_log(
    db: Session,
    user_id: int | None,
    acao: str,
    recurso: str,
    detalhes: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    acao_normalizada = acao.strip().upper()
    recurso_normalizado = recurso.strip()
    log = AuditLog(
        user_id=user_id,
        acao=acao_normalizada,
        recurso=recurso_normalizado,
        detalhes=detalhes,
        ip_address=_extract_ip(request),
    )
    db.add(log)
    db.commit()

    await _avaliar_e_disparar_alerta(
        db=db,
        acao=acao_normalizada,
        recurso=recurso_normalizado,
        user_id=user_id,
        detalhes=detalhes,
        ip_address=log.ip_address,
    )


def _extrair_email_do_recurso(recurso: str) -> str | None:
    if ":" not in recurso:
        return None
    candidato = recurso.split(":")[-1].strip()
    if "@" in candidato:
        return candidato
    return None


def _deve_alertar_login_falha(db: Session, user_id: int | None, recurso: str) -> bool:
    limite_tempo = datetime.utcnow() - timedelta(minutes=10)
    query = (
        db.query(AuditLog)
        .filter(
            AuditLog.acao == "LOGIN_FALHA",
            AuditLog.timestamp >= limite_tempo,
        )
        .order_by(AuditLog.timestamp.desc())
    )
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    else:
        query = query.filter(AuditLog.recurso == recurso)

    qtd_falhas = query.limit(3).count()
    return qtd_falhas == 3


def _obter_email_usuario(db: Session, user_id: int | None, recurso: str) -> str:
    if user_id is not None:
        usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
        if usuario and usuario.email:
            return usuario.email
    email_recurso = _extrair_email_do_recurso(recurso)
    if email_recurso:
        return email_recurso
    return "desconhecido"


async def _avaliar_e_disparar_alerta(
    db: Session,
    acao: str,
    recurso: str,
    user_id: int | None,
    detalhes: dict[str, Any] | None,
    ip_address: str | None,
) -> None:
    config_sistema = db.query(ConfiguracaoSistema).filter(ConfiguracaoSistema.id == 1).first()
    admin_number = (
        config_sistema.admin_whatsapp_number
        if config_sistema and config_sistema.admin_whatsapp_number
        else os.getenv("ADMIN_WHATSAPP_NUMBER", "")
    ).strip()
    if not admin_number:
        return

    acao_critica = acao in {"ALTERAR_CONFIGURACOES", "DELETAR_CLIENTE"}
    login_critico = acao == "LOGIN_FALHA" and _deve_alertar_login_falha(db=db, user_id=user_id, recurso=recurso)
    if not acao_critica and not login_critico:
        return

    config = db.query(FerrioliConfig).first()
    if not config:
        return

    usuario_email = _obter_email_usuario(db=db, user_id=user_id, recurso=recurso)
    detalhes_texto = str(detalhes or {})
    mensagem = (
        "⚠️ *ALERTA DE SEGURANCA - FERRIOLI ADS* ⚠️\n\n"
        "Uma acao critica foi detectada:\n"
        f"*Acao:* {acao}\n"
        f"*Usuario:* {usuario_email}\n"
        f"*IP:* {ip_address or '-'}\n"
        f"*Detalhes:* {detalhes_texto}\n\n"
        "Verifique o painel de logs para mais informacoes."
    )

    try:
        EvolutionService().enviar_texto_whatsapp(
            config=config,
            numero_destino=admin_number,
            mensagem=mensagem,
        )
    except Exception:
        return


def registrar_log_safe(
    db: Session,
    user_id: int | None,
    acao: str,
    recurso: str,
    detalhes: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    try:
        asyncio.run(
            registrar_log(
                db=db,
                user_id=user_id,
                acao=acao,
                recurso=recurso,
                detalhes=detalhes,
                request=request,
            )
        )
    except RuntimeError:
        acao_normalizada = acao.strip().upper()
        recurso_normalizado = recurso.strip()
        ip_address = _extract_ip(request)
        log = AuditLog(
            user_id=user_id,
            acao=acao_normalizada,
            recurso=recurso_normalizado,
            detalhes=detalhes,
            ip_address=ip_address,
        )
        db.add(log)
        db.commit()
        try:
            asyncio.run(
                _avaliar_e_disparar_alerta(
                    db=db,
                    acao=acao_normalizada,
                    recurso=recurso_normalizado,
                    user_id=user_id,
                    detalhes=detalhes,
                    ip_address=ip_address,
                )
            )
        except Exception:
            return
