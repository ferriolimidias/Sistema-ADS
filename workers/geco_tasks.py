import asyncio
import logging
from datetime import datetime

from api.utils.audit import registrar_log_safe
from engines.ai_engine.strategist import analisar_termos_sujos
from engines.google_engine.collector import GoogleCollector
from engines.google_engine.launcher import GoogleAdsLauncher
from engines.google_engine.metrics import GoogleMetricsCollector
from engines.meta_engine.collector import MetaCollector
from engines.meta_engine.launcher import MetaAdsLauncher
from engines.utils.evolution_service import EvolutionService
from models.database import get_db
from models.schema import Campanha, Cliente, ConfiguracaoSistema, FerrioliConfig, LogOtimizacaoGECO, MetricasDiarias
from sqlalchemy import or_
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


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


def _formatar_brl(valor: float) -> str:
    return f"R$ {float(valor or 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _upsert_metricas_diarias_collector(
    db,
    campanha_id: int,
    spend: float,
    conversoes: int,
    servicos: list[dict] | None = None,
) -> None:
    """Cria ou atualiza metricas do dia por servico; fallback agregado quando nao houver granularidade."""
    hoje = datetime.utcnow().date()

    servicos_norm = [item for item in (servicos or []) if (item or {}).get("nome_servico")]
    if not servicos_norm:
        row = (
            db.query(MetricasDiarias)
            .filter(
                MetricasDiarias.campanha_id == campanha_id,
                MetricasDiarias.data == hoje,
                MetricasDiarias.nome_servico.is_(None),
            )
            .first()
        )
        if row:
            row.spend = float(spend)
            row.conversoes = int(conversoes)
        else:
            db.add(
                MetricasDiarias(
                    campanha_id=campanha_id,
                    data=hoje,
                    nome_servico=None,
                    spend=float(spend),
                    conversoes=int(conversoes),
                    receita=0.0,
                )
            )
        return

    for servico in servicos_norm:
        nome_servico = str((servico or {}).get("nome_servico") or "").strip() or None
        if not nome_servico:
            continue
        spend_servico = float((servico or {}).get("spend", 0.0) or 0.0)
        conversoes_servico = int((servico or {}).get("conversions", 0) or 0)
        row = (
            db.query(MetricasDiarias)
            .filter(
                MetricasDiarias.campanha_id == campanha_id,
                MetricasDiarias.data == hoje,
                MetricasDiarias.nome_servico == nome_servico,
            )
            .first()
        )
        if row:
            row.spend = spend_servico
            row.conversoes = conversoes_servico
        else:
            db.add(
                MetricasDiarias(
                    campanha_id=campanha_id,
                    data=hoje,
                    nome_servico=nome_servico,
                    spend=spend_servico,
                    conversoes=conversoes_servico,
                    receita=0.0,
                )
            )


@celery_app.task(name="workers.geco_tasks.otimizador_geco_cortar_sangria")
def otimizador_geco_cortar_sangria():
    db_generator = get_db()
    db = next(db_generator)

    try:
        ferrioli_config = db.query(FerrioliConfig).first()
        if not ferrioli_config:
            logger.warning("GECO abortado: nenhuma configuracao master encontrada em Ferrioli_Config.")
            return

        campanhas_ativas = db.query(Campanha).filter(Campanha.status == "ATIVA").all()
        for campanha in campanhas_ativas:
            logger.info(
                "Iniciando analise GECO para a campanha ID: %s. Verificando limite de CPA e regras de escala.",
                campanha.id,
            )

            plataforma = (campanha.plataforma or "").upper()
            campanha_plataforma_id = campanha.plataforma_campanha_id or campanha.id_plataforma
            cliente = None

            if not campanha_plataforma_id:
                logger.warning(
                    "GECO ignorando campanha %s por falta de identificador de plataforma.",
                    campanha.id,
                )
                continue

            metricas = None
            if plataforma == "META":
                meta_credentials = _montar_meta_credentials(ferrioli_config)
                metricas = MetaCollector().obter_metricas_campanha(
                    campanha_id=campanha_plataforma_id,
                    credentials_dict=meta_credentials,
                )
            elif plataforma == "GOOGLE":
                cliente = db.query(Cliente).filter(Cliente.id == campanha.cliente_id).first()
                if not cliente or not cliente.google_customer_id:
                    logger.warning(
                        "GECO nao conseguiu coletar metricas da campanha Google %s por falta de google_customer_id.",
                        campanha.id,
                    )
                    continue

                google_credentials = _montar_google_credentials(ferrioli_config)
                metricas = GoogleCollector().obter_metricas_campanha(
                    customer_id=cliente.google_customer_id,
                    campanha_id=campanha_plataforma_id,
                    credentials_dict=google_credentials,
                )
            else:
                logger.warning(
                    "GECO ignorando campanha %s por plataforma nao suportada: %s",
                    campanha.id,
                    campanha.plataforma,
                )
                continue

            spend = float(metricas.get("spend", 0.0))
            conversions = int(metricas.get("conversions", 0))
            _upsert_metricas_diarias_collector(
                db=db,
                campanha_id=campanha.id,
                spend=spend,
                conversoes=conversions,
                servicos=metricas.get("servicos", []),
            )
            db.commit()

            limite_critico = float(campanha.orcamento_diario or 0.0) * 0.5

            if spend > limite_critico and conversions == 0:
                logger.warning(
                    "GECO Acao: Campanha %s (%s) gastou %.2f sem conversoes. Acionando API para PAUSAR.",
                    campanha.id,
                    campanha.plataforma,
                    spend,
                )
                pausa_executada = False

                if plataforma == "META":
                    meta_credentials = _montar_meta_credentials(ferrioli_config)
                    pausa_executada = MetaAdsLauncher().pausar_campanha(
                        plataforma_campanha_id=campanha_plataforma_id,
                        credentials_dict=meta_credentials,
                    )
                elif plataforma == "GOOGLE":
                    if not cliente or not cliente.google_customer_id:
                        logger.warning(
                            "GECO nao conseguiu pausar campanha Google %s por falta de google_customer_id.",
                            campanha.id,
                        )
                        continue

                    google_credentials = _montar_google_credentials(ferrioli_config)
                    pausa_executada = asyncio.run(
                        GoogleAdsLauncher().pausar_campanha(
                            customer_id=cliente.google_customer_id,
                            plataforma_campanha_id=campanha_plataforma_id,
                            credentials_dict=google_credentials,
                        )
                    )

                if pausa_executada:
                    campanha.status = "PAUSADA"
                    log_otimizacao = LogOtimizacaoGECO(
                        campanha_id=campanha.id,
                        acao_tomada="PAUSA_SANGRIA",
                        motivo="Gasto excedeu 50% da verba diária sem conversões",
                        metricas_no_momento=metricas,
                    )
                    db.add(log_otimizacao)
                    db.commit()
                    logger.info(
                        "GECO pausou a campanha %s e registrou auditoria em Log_Otimizacao_GECO.",
                        campanha.id,
                    )

        logger.info("GECO finalizou o ciclo de analise das campanhas ativas.")
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


@celery_app.task(name="workers.geco_tasks.otimizador_geco_escala_vertical")
def otimizador_geco_escala_vertical():
    db_generator = get_db()
    db = next(db_generator)

    try:
        ferrioli_config = db.query(FerrioliConfig).first()
        if not ferrioli_config:
            logger.warning("GECO escala abortado: nenhuma configuracao master encontrada em Ferrioli_Config.")
            return

        campanhas_elegiveis = (
            db.query(Campanha)
            .filter(
                Campanha.status == "ATIVA",
                Campanha.cpa_alvo.isnot(None),
                Campanha.orcamento_diario > 0,
            )
            .all()
        )

        for campanha in campanhas_elegiveis:
            logger.info(
                "Iniciando analise de escala vertical GECO para campanha ID: %s.",
                campanha.id,
            )

            plataforma = (campanha.plataforma or "").upper()
            campanha_plataforma_id = campanha.plataforma_campanha_id or campanha.id_plataforma
            cliente = None

            if not campanha_plataforma_id:
                logger.warning(
                    "GECO escala ignorando campanha %s por falta de identificador de plataforma.",
                    campanha.id,
                )
                continue

            metricas = None
            if plataforma == "META":
                meta_credentials = _montar_meta_credentials(ferrioli_config)
                metricas = MetaCollector().obter_metricas_campanha(
                    campanha_id=campanha_plataforma_id,
                    credentials_dict=meta_credentials,
                )
            elif plataforma == "GOOGLE":
                cliente = db.query(Cliente).filter(Cliente.id == campanha.cliente_id).first()
                if not cliente or not cliente.google_customer_id:
                    logger.warning(
                        "GECO escala nao conseguiu coletar metricas da campanha Google %s por falta de google_customer_id.",
                        campanha.id,
                    )
                    continue

                google_credentials = _montar_google_credentials(ferrioli_config)
                metricas = GoogleCollector().obter_metricas_campanha(
                    customer_id=cliente.google_customer_id,
                    campanha_id=campanha_plataforma_id,
                    credentials_dict=google_credentials,
                )
            else:
                logger.warning(
                    "GECO escala ignorando campanha %s por plataforma nao suportada: %s",
                    campanha.id,
                    campanha.plataforma,
                )
                continue

            conversions = int(metricas.get("conversions", 0))
            spend = float(metricas.get("spend", 0.0))
            _upsert_metricas_diarias_collector(
                db=db,
                campanha_id=campanha.id,
                spend=spend,
                conversoes=conversions,
                servicos=metricas.get("servicos", []),
            )
            db.commit()

            cpa = float(metricas.get("cpa", 0.0))
            limite_escala = float(campanha.cpa_alvo or 0.0) * 0.85

            if conversions >= 3 and cpa <= limite_escala:
                novo_orcamento = float(campanha.orcamento_diario) * 1.15
                escala_executada = False

                if plataforma == "META":
                    meta_credentials = _montar_meta_credentials(ferrioli_config)
                    escala_executada = asyncio.run(
                        MetaAdsLauncher().atualizar_orcamento_diario(
                            plataforma_campanha_id=campanha_plataforma_id,
                            novo_valor=novo_orcamento,
                            credentials_dict=meta_credentials,
                        )
                    )
                elif plataforma == "GOOGLE":
                    if not cliente or not cliente.google_customer_id:
                        logger.warning(
                            "GECO escala nao conseguiu atualizar campanha Google %s por falta de google_customer_id.",
                            campanha.id,
                        )
                        continue

                    google_credentials = _montar_google_credentials(ferrioli_config)
                    escala_executada = asyncio.run(
                        GoogleAdsLauncher().atualizar_orcamento_diario(
                            customer_id=cliente.google_customer_id,
                            plataforma_campanha_id=campanha_plataforma_id,
                            novo_valor=novo_orcamento,
                            credentials_dict=google_credentials,
                        )
                    )

                if escala_executada:
                    campanha.orcamento_diario = novo_orcamento
                    log_otimizacao = LogOtimizacaoGECO(
                        campanha_id=campanha.id,
                        acao_tomada="ESCALA_VERBA",
                        motivo=(
                            f"CPA atual ({cpa}) está 15% abaixo do alvo ({campanha.cpa_alvo}). "
                            f"Orçamento aumentado para {novo_orcamento}."
                        ),
                        metricas_no_momento=metricas,
                    )
                    db.add(log_otimizacao)
                    db.commit()
                    logger.info(
                        "GECO escalou a campanha %s e atualizou o orcamento diario para %.2f.",
                        campanha.id,
                        novo_orcamento,
                    )

        logger.info("GECO finalizou o ciclo de escala vertical das campanhas ativas.")
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass


@celery_app.task(name="limpeza_termos_intraday")
def limpeza_termos_intraday():
    db_generator = get_db()
    db = next(db_generator)
    try:
        config_sistema = db.query(ConfiguracaoSistema).filter(ConfiguracaoSistema.id == 1).first()
        if not config_sistema:
            config_sistema = ConfiguracaoSistema(id=1, intraday_cleaner_enabled=False, admin_whatsapp_number=None)
            db.add(config_sistema)
            db.commit()
            db.refresh(config_sistema)

        if not bool(config_sistema.intraday_cleaner_enabled):
            logger.info("Limpeza intra-day desativada via painel (ConfiguracaoSistema.intraday_cleaner_enabled).")
            return "Task desativada via painel"

        ferrioli_config = db.query(FerrioliConfig).first()
        if not ferrioli_config:
            logger.warning("Limpeza intra-day abortada: configuracao master nao encontrada.")
            return {"status": "erro", "motivo": "configuracao_ausente"}

        campanhas_google_ativas = (
            db.query(Campanha)
            .filter(
                Campanha.status == "ATIVA",
                or_(
                    Campanha.plataforma == "GOOGLE",
                    Campanha.tipo.ilike("%GOOGLE%"),
                ),
            )
            .all()
        )
        if not campanhas_google_ativas:
            logger.info("Limpeza intra-day: nenhuma campanha Google ativa.")
            return {"status": "sucesso", "campanhas_processadas": 0, "termos_negativados": 0}

        google_credentials = _montar_google_credentials(ferrioli_config)
        collector = GoogleMetricsCollector()
        launcher = GoogleAdsLauncher()
        campanhas_afetadas: list[str] = []
        total_negativados = 0
        economia_total_estimada = 0.0

        for campanha in campanhas_google_ativas:
            campanha_plataforma_id = (campanha.plataforma_campanha_id or campanha.id_plataforma or "").strip()
            if not campanha_plataforma_id:
                continue
            cliente = db.query(Cliente).filter(Cliente.id == campanha.cliente_id).first()
            if not cliente or not cliente.google_customer_id:
                continue

            termos = collector.fetch_search_terms(
                customer_id=cliente.google_customer_id,
                campaign_id=campanha_plataforma_id,
                periodo_dias=2,
                credentials_dict=google_credentials,
            )
            if not termos:
                continue

            termos_por_adgroup: dict[tuple[str, str], list[dict]] = {}
            for termo in termos:
                ad_group_id = str(termo.get("ad_group_id", "") or "").strip()
                nome_servico = str(termo.get("nome_servico", "") or "").strip() or "SERVICO"
                search_term = str(termo.get("search_term", "") or "").strip()
                if not ad_group_id or not search_term:
                    continue
                chave = (ad_group_id, nome_servico)
                termos_por_adgroup.setdefault(chave, []).append(termo)

            campanha_teve_acao = False
            for (ad_group_id, nome_servico), termos_grupo in termos_por_adgroup.items():
                termos_grupo_ordenados = sorted(
                    termos_grupo,
                    key=lambda x: float(x.get("cost", 0.0) or 0.0),
                    reverse=True,
                )[:120]
                payload_ia = [
                    {
                        "search_term": item.get("search_term"),
                        "clicks": int(item.get("clicks", 0) or 0),
                        "cost": float(item.get("cost", 0.0) or 0.0),
                        "conversions": float(item.get("conversions", 0.0) or 0.0),
                    }
                    for item in termos_grupo_ordenados
                ]
                if not payload_ia:
                    continue

                try:
                    analise = asyncio.run(
                        analisar_termos_sujos(
                            termos_lista=payload_ia,
                            nome_servico=nome_servico,
                            openai_api_key=ferrioli_config.openai_api_key,
                        )
                    )
                except Exception:
                    logger.exception(
                        "Falha na analise de termos intra-day. campanha_id=%s ad_group=%s",
                        campanha.id,
                        ad_group_id,
                    )
                    continue

                termos_negativar = [
                    str(item or "").strip()
                    for item in (analise.get("termos_negativar") or [])
                    if str(item or "").strip()
                ]
                if not termos_negativar:
                    continue

                resultado = asyncio.run(
                    launcher.negativar_termos_adgroup(
                        customer_id=cliente.google_customer_id,
                        ad_group_id=ad_group_id,
                        lista_termos=termos_negativar,
                        credentials_dict=google_credentials,
                    )
                )
                negativados = resultado.get("negativados", []) if resultado.get("sucesso") else []
                if not negativados:
                    continue

                campanha_teve_acao = True
                total_negativados += len(negativados)
                custos_por_termo = {
                    str(item.get("search_term", "")).strip().lower(): float(item.get("cost", 0.0) or 0.0)
                    for item in termos_grupo_ordenados
                }
                for termo in negativados:
                    custo_2d = float(custos_por_termo.get(str(termo).lower(), 0.0))
                    economia_mensal = (custo_2d / 2.0) * 30.0
                    economia_total_estimada += economia_mensal
                    try:
                        registrar_log_safe(
                            db=db,
                            user_id=None,
                            acao="NEGATIVAR_TERMO",
                            recurso=f"Campanha #{campanha.id} - {nome_servico}",
                            detalhes={
                                "origem": "LIMPEZA_INTRADAY",
                                "campanha_id": campanha.id,
                                "campanha_plataforma_id": campanha_plataforma_id,
                                "ad_group_id": ad_group_id,
                                "nome_servico": nome_servico,
                                "termo_negativado": termo,
                                "periodo_dias_ref": 2,
                                "custo_periodo_termo": round(custo_2d, 4),
                                "economia_mensal_estimada": round(economia_mensal, 4),
                            },
                            request=None,
                        )
                    except Exception:
                        logger.exception("Falha ao registrar AuditLog do termo negativado intra-day.")

                db.commit()

            if campanha_teve_acao:
                campanhas_afetadas.append(f"#{campanha.id} {cliente.nome}")

        if total_negativados > 0:
            admin_number = str(config_sistema.admin_whatsapp_number or "").strip()
            if admin_number:
                try:
                    EvolutionService().enviar_alerta_ai_cleaner_intraday(
                        config=ferrioli_config,
                        numero_destino=admin_number,
                        termos_negativados=total_negativados,
                        economia_estimada_brl=_formatar_brl(economia_total_estimada),
                        campanhas_afetadas=campanhas_afetadas,
                    )
                except Exception:
                    logger.exception("Falha ao enviar alerta WhatsApp da limpeza intra-day.")

        logger.info(
            "Limpeza intra-day finalizada. campanhas=%s negativados=%s economia=%.2f",
            len(campanhas_google_ativas),
            total_negativados,
            economia_total_estimada,
        )
        return {
            "status": "sucesso",
            "campanhas_processadas": len(campanhas_google_ativas),
            "termos_negativados": int(total_negativados),
            "economia_estimada": round(economia_total_estimada, 2),
            "campanhas_afetadas": campanhas_afetadas,
        }
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass
