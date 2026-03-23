import asyncio
import logging
from datetime import datetime

from engines.google_engine.collector import GoogleCollector
from engines.google_engine.launcher import GoogleAdsLauncher
from engines.meta_engine.collector import MetaCollector
from engines.meta_engine.launcher import MetaAdsLauncher
from models.database import get_db
from models.schema import Campanha, Cliente, FerrioliConfig, LogOtimizacaoGECO, MetricasDiarias
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
