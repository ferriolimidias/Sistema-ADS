import json
import logging
import os
from typing import Any

from api.utils.ai_config import MODEL_ANALYSIS
from openai import AsyncOpenAI
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.schema import MetricasDiarias

logger = logging.getLogger(__name__)


def _build_prompt(dados_performance: dict[str, Any]) -> str:
    cliente = dados_performance.get("cliente") or "Cliente"
    dados_serializados = json.dumps(dados_performance, ensure_ascii=False, indent=2)
    return (
        "Aja como um Gestor de Trafego Senior. Analise os dados de "
        f"{cliente} e identifique: 1. O servico com melhor retorno, "
        "2. Um servico que pode ser otimizado, 3. Uma sugestao de realocacao de verba. "
        "Seja curto, direto e use tom profissional.\n\n"
        "Dados de performance:\n"
        f"{dados_serializados}"
    )


def _estimar_tokens_por_texto(texto: str) -> int:
    return max(1, int(len(str(texto or "")) / 4))


def _log_modelo_e_tokens(task: str, model: str, response: Any, payload_referencia: str) -> None:
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
    total_tokens = getattr(usage, "total_tokens", None) if usage else None
    if total_tokens is None:
        prompt_est = _estimar_tokens_por_texto(payload_referencia)
        completion_est = 120
        total_est = prompt_est + completion_est
        logger.info(
            "[AI][%s] modelo=%s tokens_estimados=%s (prompt~%s completion~%s)",
            task,
            model,
            total_est,
            prompt_est,
            completion_est,
        )
        return
    logger.info(
        "[AI][%s] modelo=%s tokens=%s (prompt=%s completion=%s)",
        task,
        model,
        total_tokens,
        prompt_tokens,
        completion_tokens,
    )


def montar_dados_performance_reais_por_servico(
    db: Session,
    campanha_id: int,
    cliente_nome: str,
) -> dict[str, Any]:
    rows = (
        db.query(
            func.coalesce(MetricasDiarias.nome_servico, "SERVICO_NAO_IDENTIFICADO").label("nome_servico"),
            func.coalesce(func.sum(MetricasDiarias.spend), 0.0).label("gasto"),
            func.coalesce(func.sum(MetricasDiarias.conversoes), 0).label("conversoes"),
            func.coalesce(func.sum(MetricasDiarias.receita), 0.0).label("receita"),
        )
        .filter(MetricasDiarias.campanha_id == campanha_id)
        .group_by(func.coalesce(MetricasDiarias.nome_servico, "SERVICO_NAO_IDENTIFICADO"))
        .all()
    )

    servicos = []
    for row in rows:
        gasto = float(row.gasto or 0.0)
        receita = float(row.receita or 0.0)
        roas = (receita / gasto) if gasto > 0 and receita > 0 else None
        servicos.append(
            {
                "nome": str(row.nome_servico),
                "gasto": round(gasto, 2),
                "conversoes": int(row.conversoes or 0),
                "roas": (round(roas, 2) if roas is not None else None),
            }
        )

    return {
        "cliente": cliente_nome,
        "campanha_id": campanha_id,
        "servicos": servicos,
    }


async def gerar_insight_estrategico(
    dados_performance: dict[str, Any],
    openai_api_key: str | None = None,
) -> str:
    api_key = (openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY nao configurada para gerar insight estrategico.")

    model = MODEL_ANALYSIS
    client = AsyncOpenAI(api_key=api_key, timeout=12.0)
    prompt = _build_prompt(dados_performance)
    response = await client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        temperature=0.4,
        messages=[
            {
                "role": "system",
                "content": (
                    "Voce gera insights executivos curtos, objetivos e acionaveis para campanhas de midia paga. "
                    "Retorne apenas JSON no formato {\"insight\":\"texto\"}."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    _log_modelo_e_tokens("gerar_insight_estrategico", model, response, prompt)
    content = (response.choices[0].message.content or "{}").strip()
    parsed = json.loads(content)
    insight = str(parsed.get("insight") or "").strip()
    if not insight:
        raise ValueError("A IA nao retornou insight.")
    return insight[:1200]


async def analisar_termos_sujos(
    termos_lista: list[dict[str, Any]] | list[str],
    nome_servico: str,
    openai_api_key: str | None = None,
) -> dict[str, Any]:
    api_key = (openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY nao configurada para analise de termos.")

    termos_serializados = json.dumps(termos_lista or [], ensure_ascii=False)
    prompt = (
        f"Analise estes termos de busca para o servico '{nome_servico}'. "
        "Identifique termos que sao irrelevantes, curiosos, procuram por cursos/gratis "
        "ou concorrentes nao relacionados. Retorne apenas um JSON com a lista de termos para negativar.\n\n"
        "Formato de resposta obrigatorio:\n"
        '{"termos_negativar": ["termo 1", "termo 2"]}\n\n'
        f"Termos:\n{termos_serializados}"
    )

    model = MODEL_ANALYSIS
    client = AsyncOpenAI(api_key=api_key, timeout=18.0)
    response = await client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": "Voce analisa termos de busca e retorna apenas JSON valido.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    _log_modelo_e_tokens("analisar_termos_sujos", model, response, prompt)
    content = (response.choices[0].message.content or "{}").strip()
    data = json.loads(content)
    termos = data.get("termos_negativar", [])
    if not isinstance(termos, list):
        termos = []
    termos_limpos: list[str] = []
    for termo in termos:
        valor = str(termo or "").strip()
        if valor and valor.lower() not in {item.lower() for item in termos_limpos}:
            termos_limpos.append(valor)
    return {"termos_negativar": termos_limpos}
