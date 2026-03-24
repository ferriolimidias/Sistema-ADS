import json
import logging
import os
from typing import Any

from api.utils.ai_config import MODEL_ANALYSIS, registrar_consumo_ia
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
        registrar_consumo_ia(
            db=None,
            modelo=model,
            tokens_in=prompt_est,
            tokens_out=completion_est,
            tarefa=task,
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
    registrar_consumo_ia(
        db=None,
        modelo=model,
        tokens_in=int(prompt_tokens or 0),
        tokens_out=int(completion_tokens or 0),
        tarefa=task,
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
    _log_modelo_e_tokens("Insight Estratégico", model, response, prompt)
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
    _log_modelo_e_tokens("Limpeza de Termos", model, response, prompt)
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


async def analisar_performance_dispositivos(
    dados_dispositivos: list[dict[str, Any]],
    openai_api_key: str | None = None,
) -> dict[str, Any]:
    dispositivos = []
    total_cost = 0.0
    total_conv = 0.0
    for item in dados_dispositivos or []:
        device = str(item.get("device", "") or "").strip().upper() or "UNSPECIFIED"
        cost = float(item.get("cost", 0.0) or 0.0)
        conv = float(item.get("conversions", 0.0) or 0.0)
        cpa = (cost / conv) if conv > 0 else None
        total_cost += cost
        total_conv += conv
        dispositivos.append(
            {
                "device": device,
                "clicks": int(item.get("clicks", 0) or 0),
                "impressions": int(item.get("impressions", 0) or 0),
                "cost": round(cost, 4),
                "conversions": round(conv, 2),
                "cpa": (round(cpa, 4) if cpa is not None else None),
            }
        )

    media_cpa = (total_cost / total_conv) if total_conv > 0 else None
    sugestoes: list[dict[str, Any]] = []
    sugestoes_base: list[dict[str, Any]] = []
    if media_cpa and media_cpa > 0:
        limiar_ruim = media_cpa * 1.2
        limiar_critico = media_cpa * 1.5
        limiar_mobile_bom = media_cpa * 0.85
        for item in dispositivos:
            cpa = item.get("cpa")
            cost = float(item.get("cost", 0.0) or 0.0)
            conv = float(item.get("conversions", 0.0) or 0.0)
            device = str(item.get("device", "UNSPECIFIED"))
            if conv <= 0 and cost >= (float(media_cpa) * 2.0):
                sugestoes_base.append(
                    {
                        "dispositivo": device,
                        "ajuste_percentual": -20,
                        "justificativa": (
                            f"Gasto elevado sem conversao ({cost:.2f}) no periodo. "
                            "Reduzir exposicao para conter desperdicio."
                        ),
                        "severidade": "ALTA",
                    }
                )
                continue
            if cpa is None:
                continue
            if float(cpa) > limiar_critico:
                sugestoes_base.append(
                    {
                        "dispositivo": device,
                        "ajuste_percentual": -20,
                        "justificativa": (
                            f"CPA ({float(cpa):.2f}) acima de 50% da media da campanha "
                            f"({float(media_cpa):.2f})."
                        ),
                        "severidade": "ALTA",
                    }
                )
            elif float(cpa) > limiar_ruim:
                sugestoes_base.append(
                    {
                        "dispositivo": device,
                        "ajuste_percentual": -15,
                        "justificativa": (
                            f"CPA ({float(cpa):.2f}) acima de 20% da media da campanha "
                            f"({float(media_cpa):.2f})."
                        ),
                        "severidade": "MEDIA",
                    }
                )
            elif device == "MOBILE" and float(cpa) <= limiar_mobile_bom and float(item.get("conversions", 0.0) or 0.0) > 0:
                sugestoes_base.append(
                    {
                        "dispositivo": device,
                        "ajuste_percentual": 10,
                        "justificativa": (
                            f"Mobile com CPA excelente ({float(cpa):.2f}) abaixo da media "
                            f"({float(media_cpa):.2f}). Priorizar entrega."
                        ),
                        "severidade": "BAIXA",
                    }
                )
    sugestoes = [dict(item) for item in sugestoes_base]

    resumo_ia = ""
    api_key = (openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    if api_key:
        prompt = (
            "Analise performance por dispositivo e retorne JSON com resumo e sugestoes. "
            "Use as sugestoes pre-calculadas como base e ajuste apenas se necessario.\n\n"
            f"Dados: {json.dumps(dispositivos, ensure_ascii=False)}\n"
            f"Media CPA: {round(float(media_cpa or 0.0), 4)}\n"
            f"Sugestoes base: {json.dumps(sugestoes_base, ensure_ascii=False)}\n\n"
            "Formato obrigatorio:\n"
            '{"resumo":"texto","sugestoes":[{"dispositivo":"MOBILE","ajuste_percentual":-15,"justificativa":"...","severidade":"ALTA|MEDIA|BAIXA"}]}'
        )
        model = MODEL_ANALYSIS
        client = AsyncOpenAI(api_key=api_key, timeout=14.0)
        response = await client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Voce e especialista em performance de Google Ads. "
                        "Retorne apenas JSON valido com resumo e sugestoes contendo severidade."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        _log_modelo_e_tokens("Analise Dispositivos", model, response, prompt)
        content = (response.choices[0].message.content or "{}").strip()
        parsed = json.loads(content)
        resumo_ia = str(parsed.get("resumo") or "").strip()
        sugestoes_ia = parsed.get("sugestoes", [])
        if isinstance(sugestoes_ia, list) and sugestoes_ia:
            sugestoes = []
            for item in sugestoes_ia:
                dispositivo = str((item or {}).get("dispositivo", "")).strip().upper()
                if not dispositivo:
                    continue
                severidade = str((item or {}).get("severidade", "MEDIA")).strip().upper()
                if severidade not in {"ALTA", "MEDIA", "BAIXA"}:
                    severidade = "MEDIA"
                sugestoes.append(
                    {
                        "dispositivo": dispositivo,
                        "ajuste_percentual": float((item or {}).get("ajuste_percentual", 0.0) or 0.0),
                        "justificativa": str((item or {}).get("justificativa", "")).strip(),
                        "severidade": severidade,
                    }
                )
        if not sugestoes:
            sugestoes = [dict(item) for item in sugestoes_base]

    for sugestao in sugestoes:
        if "severidade" not in sugestao:
            sugestao["severidade"] = "MEDIA"

    return {
        "media_cpa": (round(float(media_cpa), 4) if media_cpa is not None else None),
        "dispositivos": dispositivos,
        "sugestoes": sugestoes,
        "resumo_ia": resumo_ia,
    }


async def analisar_performance_horarios(
    dados_horarios: list[dict[str, Any]],
    openai_api_key: str | None = None,
) -> dict[str, Any]:
    horarios = []
    total_cost = 0.0
    total_conv = 0.0
    for item in dados_horarios or []:
        hora = int(item.get("hour_of_day", 0) or 0)
        dia_semana = str(item.get("day_of_week", "UNSPECIFIED") or "UNSPECIFIED").strip().upper()
        clicks = int(item.get("clicks", 0) or 0)
        cost = float(item.get("cost", 0.0) or 0.0)
        conv = float(item.get("conversions", 0.0) or 0.0)
        cpa = (cost / conv) if conv > 0 else None
        total_cost += cost
        total_conv += conv
        horarios.append(
            {
                "hour_of_day": hora,
                "day_of_week": dia_semana,
                "clicks": clicks,
                "cost": round(cost, 4),
                "conversions": round(conv, 2),
                "cpa": (round(cpa, 4) if cpa is not None else None),
            }
        )

    media_cpa = (total_cost / total_conv) if total_conv > 0 else None
    media_conv_slot = (total_conv / len(horarios)) if horarios else 0.0
    sugestoes_base: list[dict[str, Any]] = []
    if media_cpa and media_cpa > 0:
        for item in horarios:
            hora = int(item.get("hour_of_day", 0) or 0)
            dia = str(item.get("day_of_week", "UNSPECIFIED"))
            conv = float(item.get("conversions", 0.0) or 0.0)
            cost = float(item.get("cost", 0.0) or 0.0)
            cpa = item.get("cpa")
            if conv <= 0 and cost >= float(media_cpa):
                severidade = "ALTA" if cost >= float(media_cpa) * 1.5 else "MEDIA"
                ajuste = -25 if severidade == "ALTA" else -15
                sugestoes_base.append(
                    {
                        "dia_semana": dia,
                        "hora_inicio": hora,
                        "hora_fim": min(24, hora + 1),
                        "ajuste_percentual": ajuste,
                        "severidade": severidade,
                        "justificativa": (
                            f"Vale de conversao: custo {cost:.2f} sem leads no slot {dia} {hora:02d}h-{min(24, hora + 1):02d}h."
                        ),
                    }
                )
                continue
            if cpa is not None and float(cpa) > float(media_cpa) * 1.3:
                sugestoes_base.append(
                    {
                        "dia_semana": dia,
                        "hora_inicio": hora,
                        "hora_fim": min(24, hora + 1),
                        "ajuste_percentual": -10,
                        "severidade": "MEDIA",
                        "justificativa": (
                            f"CPA do horario ({float(cpa):.2f}) acima da media da campanha ({float(media_cpa):.2f})."
                        ),
                    }
                )
            elif conv > max(1.0, media_conv_slot * 1.3) and cpa is not None and float(cpa) <= float(media_cpa) * 0.9:
                sugestoes_base.append(
                    {
                        "dia_semana": dia,
                        "hora_inicio": hora,
                        "hora_fim": min(24, hora + 1),
                        "ajuste_percentual": 10,
                        "severidade": "BAIXA",
                        "justificativa": (
                            f"Pico de conversao com eficiencia no slot {dia} {hora:02d}h-{min(24, hora + 1):02d}h."
                        ),
                    }
                )

    sugestoes = [dict(item) for item in sugestoes_base]
    resumo_ia = ""
    api_key = (openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    if api_key:
        prompt = (
            "Analise dayparting da campanha e devolva JSON com resumo e sugestoes por dia/horario.\n\n"
            f"Dados horarios: {json.dumps(horarios, ensure_ascii=False)}\n"
            f"Media CPA: {round(float(media_cpa or 0.0), 4)}\n"
            f"Sugestoes base: {json.dumps(sugestoes_base, ensure_ascii=False)}\n\n"
            "Formato obrigatorio:\n"
            '{"resumo":"texto","sugestoes":[{"dia_semana":"MONDAY","hora_inicio":8,"hora_fim":18,"ajuste_percentual":10,"severidade":"ALTA|MEDIA|BAIXA","justificativa":"..."}]}'
        )
        model = MODEL_ANALYSIS
        client = AsyncOpenAI(api_key=api_key, timeout=14.0)
        response = await client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Voce e especialista em dayparting para Google Ads. "
                        "Retorne apenas JSON valido."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        _log_modelo_e_tokens("Analise Horarios", model, response, prompt)
        content = (response.choices[0].message.content or "{}").strip()
        parsed = json.loads(content)
        resumo_ia = str(parsed.get("resumo") or "").strip()
        sugestoes_ia = parsed.get("sugestoes", [])
        if isinstance(sugestoes_ia, list) and sugestoes_ia:
            sugestoes = []
            for item in sugestoes_ia:
                severidade = str((item or {}).get("severidade", "MEDIA")).strip().upper()
                if severidade not in {"ALTA", "MEDIA", "BAIXA"}:
                    severidade = "MEDIA"
                sugestoes.append(
                    {
                        "dia_semana": str((item or {}).get("dia_semana", "UNSPECIFIED")).strip().upper(),
                        "hora_inicio": int((item or {}).get("hora_inicio", 0) or 0),
                        "hora_fim": int((item or {}).get("hora_fim", 1) or 1),
                        "ajuste_percentual": float((item or {}).get("ajuste_percentual", 0.0) or 0.0),
                        "severidade": severidade,
                        "justificativa": str((item or {}).get("justificativa", "")).strip(),
                    }
                )
        if not sugestoes:
            sugestoes = [dict(item) for item in sugestoes_base]

    return {
        "media_cpa": (round(float(media_cpa), 4) if media_cpa is not None else None),
        "horarios": horarios,
        "sugestoes": sugestoes,
        "resumo_ia": resumo_ia,
    }
