import asyncio
import logging

from engines.google_engine.collector import GoogleCollector
from engines.google_engine.launcher import GoogleAdsLauncher
from engines.meta_engine.collector import MetaCollector
from engines.meta_engine.launcher import MetaAdsLauncher
from models.database import get_db
from models.schema import Campanha, Cliente, FerrioliConfig, LogOtimizacaoGECO
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


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

            if not campanha_plataforma_id:
                logger.warning(
                    "GECO ignorando campanha %s por falta de identificador de plataforma.",
                    campanha.id,
                )
                continue

            metricas = None
            if plataforma == "META":
                meta_credentials = {
                    "meta_bm_token": ferrioli_config.meta_bm_token,
                }
                metricas = MetaCollector().obter_metricas_campanha(
                    campanha_id=campanha_plataforma_id,
                    credentials_dict=meta_credentials,
                )
            elif plataforma == "GOOGLE":
                google_credentials = {
                    "developer_token": ferrioli_config.google_mcc_token,
                    "client_id": ferrioli_config.google_ads_client_id,
                    "client_secret": ferrioli_config.google_ads_client_secret,
                    "refresh_token": ferrioli_config.google_ads_refresh_token,
                    "use_client_customer_id": ferrioli_config.google_ads_use_client_customer_id,
                }
                metricas = GoogleCollector().obter_metricas_campanha(
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
                    meta_credentials = {
                        "meta_bm_token": ferrioli_config.meta_bm_token,
                    }
                    pausa_executada = MetaAdsLauncher().pausar_campanha(
                        plataforma_campanha_id=campanha_plataforma_id,
                        credentials_dict=meta_credentials,
                    )
                elif plataforma == "GOOGLE":
                    cliente = db.query(Cliente).filter(Cliente.id == campanha.cliente_id).first()
                    if not cliente or not cliente.google_customer_id:
                        logger.warning(
                            "GECO nao conseguiu pausar campanha Google %s por falta de google_customer_id.",
                            campanha.id,
                        )
                        continue

                    google_credentials = {
                        "developer_token": ferrioli_config.google_mcc_token,
                        "client_id": ferrioli_config.google_ads_client_id,
                        "client_secret": ferrioli_config.google_ads_client_secret,
                        "refresh_token": ferrioli_config.google_ads_refresh_token,
                        "use_client_customer_id": ferrioli_config.google_ads_use_client_customer_id,
                    }
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
