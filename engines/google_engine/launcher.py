import asyncio
import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.api_core import protobuf_helpers

from engines.google_engine.geocoder import obter_coordenadas

logger = logging.getLogger(__name__)


class GoogleAdsLauncher:
    @staticmethod
    def _aparar_texto(texto: str, limite: int) -> str:
        valor = (texto or "").strip()
        return valor[:limite]

    @staticmethod
    def _normalizar_keywords(keywords: list[str]) -> list[str]:
        normalizadas: list[str] = []
        vistos: set[str] = set()

        for keyword in keywords or []:
            palavra = (keyword or "").strip().lower()
            palavra = re.sub(r'[\[\]\{\}"\'`]', "", palavra)
            palavra = re.sub(r"\s+", " ", palavra).strip()
            if not palavra:
                continue
            if len(palavra) > 80:
                continue
            if len(palavra.split()) > 10:
                continue
            if palavra in vistos:
                continue

            vistos.add(palavra)
            normalizadas.append(palavra)

        return normalizadas

    @staticmethod
    def _slugify(valor: str) -> str:
        texto = unicodedata.normalize("NFKD", str(valor or ""))
        texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
        texto = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")
        return texto or "servico"

    def _montar_url_oferta_servico(
        self,
        nome_servico: str,
        campanha_id: Optional[int],
        public_base_url: str,
        url_destino_grupo: Optional[str] = None,
        fallback_url: Optional[str] = None,
    ) -> str:
        if url_destino_grupo:
            return str(url_destino_grupo).strip()
        if campanha_id:
            base = str(public_base_url or "https://seu-dominio.com").rstrip("/")
            return f"{base}/oferta/{campanha_id}/{self._slugify(nome_servico)}"
        return str(fallback_url or "https://seu-dominio.com").strip()

    @staticmethod
    def _build_google_client(credentials_dict: dict) -> GoogleAdsClient:
        google_ads_config = dict(credentials_dict or {})
        use_client_customer_id = google_ads_config.pop("use_client_customer_id", None)
        if use_client_customer_id:
            google_ads_config["login_customer_id"] = str(use_client_customer_id).replace("-", "").strip()
        return GoogleAdsClient.load_from_dict(google_ads_config)

    def localizar_adgroup_por_nome(
        self,
        customer_id: str,
        plataforma_campanha_id: str,
        nome_servico: str,
        credentials_dict: dict,
    ) -> dict[str, Any] | None:
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        campanha_id_limpo = (plataforma_campanha_id or "").strip()
        nome_alvo = (nome_servico or "").strip().lower()
        if not customer_id_limpo or not campanha_id_limpo or not nome_alvo:
            return None
        try:
            client = self._build_google_client(credentials_dict)
            googleads_service = client.get_service("GoogleAdsService")
            query = (
                "SELECT ad_group.id, ad_group.name, ad_group.status "
                f"FROM ad_group WHERE campaign.id = {campanha_id_limpo}"
            )
            response = googleads_service.search(customer_id=customer_id_limpo, query=query)
            candidatos: list[dict[str, Any]] = []
            for row in response:
                nome = str(row.ad_group.name or "")
                if nome_alvo in nome.lower():
                    candidatos.append(
                        {
                            "ad_group_id": str(row.ad_group.id),
                            "ad_group_name": nome,
                            "status_atual": str(row.ad_group.status),
                        }
                    )
            if not candidatos:
                return None
            candidatos.sort(key=lambda item: len(item.get("ad_group_name", "")))
            return candidatos[0]
        except Exception:
            logger.exception(
                "Falha ao localizar ad group por nome. customer_id=%s campanha_id=%s nome_servico=%s",
                customer_id_limpo,
                campanha_id_limpo,
                nome_servico,
            )
            return None

    def obter_orcamento_campanha(
        self,
        customer_id: str,
        plataforma_campanha_id: str,
        credentials_dict: dict,
    ) -> float | None:
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        campanha_id_limpo = (plataforma_campanha_id or "").strip()
        try:
            client = self._build_google_client(credentials_dict)
            googleads_service = client.get_service("GoogleAdsService")
            query = (
                "SELECT campaign_budget.amount_micros "
                "FROM campaign "
                f"WHERE campaign.id = {campanha_id_limpo}"
            )
            response = googleads_service.search(customer_id=customer_id_limpo, query=query)
            for row in response:
                return float(row.campaign_budget.amount_micros or 0) / 1_000_000.0
            return None
        except Exception:
            logger.exception(
                "Falha ao obter orcamento da campanha Google. customer_id=%s campanha_id=%s",
                customer_id_limpo,
                campanha_id_limpo,
            )
            return None

    async def criar_campanha_pesquisa(
        self,
        credentials_dict: dict,
        customer_id: str,
        orcamento_diario: float,
        url_final: str,
        copy_data: dict,
        campanha_id: Optional[int] = None,
        public_base_url: str = "https://seu-dominio.com",
        cpa_alvo: Optional[float] = None,
        assets_adicionais: Optional[dict[str, Any]] = None,
        endereco_negocio: Optional[str] = None,
        raio_geografico: Optional[int] = None,
        lista_midias: Optional[list[Any]] = None,
    ):
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        maps_api_key = (credentials_dict or {}).get("Maps_api_key")
        try:
            if not customer_id_limpo:
                raise ValueError("customer_id nao informado para criacao de campanha no Google Ads.")
            if not copy_data:
                raise ValueError("copy_data nao informado para criacao de anuncio responsivo.")

            client = self._build_google_client(credentials_dict)
            campaign_budget_service = client.get_service("CampaignBudgetService")
            campaign_service = client.get_service("CampaignService")
            ad_group_service = client.get_service("AdGroupService")
            ad_group_criterion_service = client.get_service("AdGroupCriterionService")
            ad_group_ad_service = client.get_service("AdGroupAdService")
            asset_service = client.get_service("AssetService")
            ad_group_asset_service = client.get_service("AdGroupAssetService")

            # 1) Criar orcamento
            budget_operation = client.get_type("CampaignBudgetOperation")
            budget_operation.create.name = f"GECO Budget {datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            budget_operation.create.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
            budget_operation.create.amount_micros = int(float(orcamento_diario) * 1_000_000)
            budget_operation.create.explicitly_shared = False

            budget_response = campaign_budget_service.mutate_campaign_budgets(
                customer_id=customer_id_limpo,
                operations=[budget_operation],
            )
            budget_resource_name = budget_response.results[0].resource_name

            # 2) Criar campanha
            campaign_operation = client.get_type("CampaignOperation")
            campaign_operation.create.name = f"GECO - Search - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            campaign_operation.create.status = client.enums.CampaignStatusEnum.PAUSED
            campaign_operation.create.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
            campaign_operation.create.campaign_budget = budget_resource_name
            campaign_operation.create.network_settings.target_google_search = True
            campaign_operation.create.network_settings.target_search_network = False
            campaign_operation.create.network_settings.target_content_network = False
            campaign_operation.create.network_settings.target_partner_search_network = False
            if cpa_alvo and cpa_alvo > 0:
                campaign_operation.create.maximize_conversions.target_cpa_micros = int(float(cpa_alvo) * 1_000_000)

            campaign_response = campaign_service.mutate_campaigns(
                customer_id=customer_id_limpo,
                operations=[campaign_operation],
            )
            campaign_resource_name = campaign_response.results[0].resource_name
            campaign_id = campaign_resource_name.split("/")[-1]

            grupos_anuncios = copy_data.get("grupos_anuncios", []) or []
            if not grupos_anuncios:
                raise ValueError("copy_data sem grupos_anuncios para estrutura STAG.")

            # 3) e 4) STAG: cria ad group, keywords e RSA por servico
            grupos_criados = 0
            for idx, grupo in enumerate(grupos_anuncios):
                nome_servico = str(grupo.get("nome_servico", "")).strip() or f"Servico-{idx + 1}"
                palavras_chave = self._normalizar_keywords([str(item) for item in (grupo.get("palavras_chave") or [])])
                headlines = [str(item).strip() for item in (grupo.get("headlines") or []) if str(item).strip()]
                descriptions = [str(item).strip() for item in (grupo.get("descriptions") or []) if str(item).strip()]
                url_destino_grupo = str(grupo.get("url_destino", "") or "").strip() or None
                final_url_grupo = self._montar_url_oferta_servico(
                    nome_servico=nome_servico,
                    campanha_id=campanha_id,
                    public_base_url=public_base_url,
                    url_destino_grupo=url_destino_grupo,
                    fallback_url=url_final,
                )

                if not palavras_chave:
                    logger.warning("Grupo '%s' sem palavras-chave. Pulando STAG.", nome_servico)
                    continue
                if not headlines or not descriptions:
                    logger.warning("Grupo '%s' sem headlines/descriptions. Pulando STAG.", nome_servico)
                    continue

                # a) Criar AdGroup
                ad_group_operation = client.get_type("AdGroupOperation")
                ad_group_operation.create.name = f"GECO - {nome_servico[:50]} - {datetime.utcnow().strftime('%H%M%S')}"
                ad_group_operation.create.status = client.enums.AdGroupStatusEnum.PAUSED
                ad_group_operation.create.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
                ad_group_operation.create.campaign = campaign_resource_name
                ad_group_operation.create.cpc_bid_micros = 1_000_000
                ad_group_response = ad_group_service.mutate_ad_groups(
                    customer_id=customer_id_limpo,
                    operations=[ad_group_operation],
                )
                ad_group_resource_name = ad_group_response.results[0].resource_name

                # b) Criar palavras-chave no AdGroup
                keyword_operations = []
                for palavra in palavras_chave:
                    op = client.get_type("AdGroupCriterionOperation")
                    criterion = op.create
                    criterion.ad_group = ad_group_resource_name
                    criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
                    criterion.keyword.text = palavra
                    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE
                    keyword_operations.append(op)

                if keyword_operations:
                    ad_group_criterion_service.mutate_ad_group_criteria(
                        customer_id=customer_id_limpo,
                        operations=keyword_operations,
                    )

                # c) Criar RSA por grupo
                ad_group_ad_operation = client.get_type("AdGroupAdOperation")
                ad_group_ad = ad_group_ad_operation.create
                ad_group_ad.ad_group = ad_group_resource_name
                ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED
                ad_group_ad.ad.final_urls.append(final_url_grupo)

                rsa = ad_group_ad.ad.responsive_search_ad
                for headline in headlines[:15]:
                    asset = client.get_type("AdTextAsset")
                    asset.text = self._aparar_texto(headline, 30)
                    rsa.headlines.append(asset)
                for description in descriptions[:4]:
                    asset = client.get_type("AdTextAsset")
                    asset.text = self._aparar_texto(description, 90)
                    rsa.descriptions.append(asset)

                ad_group_ad_service.mutate_ad_group_ads(
                    customer_id=customer_id_limpo,
                    operations=[ad_group_ad_operation],
                )

                # d) Vincular imagens no AdGroup (STAG Images por nome_servico)
                midias_grupo = [
                    midia
                    for midia in (lista_midias or [])
                    if (midia.nome_servico or "").strip().lower() == nome_servico.strip().lower()
                ]
                if not midias_grupo:
                    midias_grupo = [
                        midia
                        for midia in (lista_midias or [])
                        if not (midia.nome_servico or "").strip()
                    ]

                for midia in midias_grupo:
                    try:
                        caminho_midia = Path(midia.caminho_arquivo)
                        if not caminho_midia.exists():
                            logger.warning(
                                "Arquivo de midia nao encontrado para injeção STAG. campanha_id=%s ad_group=%s caminho=%s",
                                campaign_id,
                                ad_group_resource_name,
                                midia.caminho_arquivo,
                            )
                            continue

                        with open(caminho_midia, "rb") as fp:
                            image_bytes = fp.read()

                        asset_operation = client.get_type("AssetOperation")
                        asset_operation.create.name = f"img-{nome_servico[:20]}-{midia.id}"
                        asset_operation.create.image_asset.data = image_bytes
                        asset_response = asset_service.mutate_assets(
                            customer_id=customer_id_limpo,
                            operations=[asset_operation],
                        )
                        image_asset_resource_name = asset_response.results[0].resource_name

                        ad_group_asset_operation = client.get_type("AdGroupAssetOperation")
                        ad_group_asset = ad_group_asset_operation.create
                        ad_group_asset.ad_group = ad_group_resource_name
                        ad_group_asset.asset = image_asset_resource_name
                        ad_group_asset.field_type = client.enums.AssetFieldTypeEnum.AD_IMAGE

                        ad_group_asset_service.mutate_ad_group_assets(
                            customer_id=customer_id_limpo,
                            operations=[ad_group_asset_operation],
                        )
                    except Exception:
                        logger.exception(
                            "Falha ao vincular imagem STAG no AdGroup. ad_group=%s midia_id=%s",
                            ad_group_resource_name,
                            getattr(midia, "id", "desconhecido"),
                        )

                grupos_criados += 1

            if grupos_criados == 0:
                raise ValueError("Nenhum grupo de anuncios STAG foi criado com sucesso.")

            if endereco_negocio and raio_geografico:
                campaign_criterion_service = client.get_service("CampaignCriterionService")
                coordenadas = await obter_coordenadas(endereco_negocio, maps_api_key) if maps_api_key else None

                if coordenadas:
                    lat, lng = coordenadas
                    campaign_criterion_operation = client.get_type("CampaignCriterionOperation")
                    criterion = campaign_criterion_operation.create
                    criterion.campaign = campaign_resource_name
                    criterion.proximity.radius = float(raio_geografico)
                    criterion.proximity.radius_units = client.enums.ProximityRadiusUnitsEnum.KILOMETERS
                    # Compatibilidade com variacoes de nomes de campo entre versoes do SDK.
                    if hasattr(criterion.proximity.geo_point, "micro_latitude"):
                        criterion.proximity.geo_point.micro_latitude = int(lat * 1_000_000)
                        criterion.proximity.geo_point.micro_longitude = int(lng * 1_000_000)
                    else:
                        criterion.proximity.geo_point.latitude_in_micro_degrees = int(lat * 1_000_000)
                        criterion.proximity.geo_point.longitude_in_micro_degrees = int(lng * 1_000_000)
                    criterion.proximity.address.street_address = endereco_negocio
                    criterion.proximity.address.country_code = "BR"

                    campaign_criterion_service.mutate_campaign_criteria(
                        customer_id=customer_id_limpo,
                        operations=[campaign_criterion_operation],
                    )
                    logger.info(
                        "Segmentacao por proximidade aplicada na campanha %s com raio=%skm.",
                        campaign_resource_name,
                        raio_geografico,
                    )
                else:
                    logger.warning(
                        "Geolocalizacao nao aplicada na campanha %s: geocoder sem coordenadas. Mantendo campanha pausada.",
                        campaign_resource_name,
                    )
            elif endereco_negocio and not raio_geografico:
                logger.warning(
                    "Endereco informado sem raio_geografico para campanha %s. Mantendo campanha pausada.",
                    campaign_resource_name,
                )
            
            if assets_adicionais:
                await self.vincular_assets(
                    customer_id=customer_id_limpo,
                    campaign_resource_name=campaign_resource_name,
                    assets_adicionais=assets_adicionais,
                    credentials_dict=credentials_dict,
                )

            logger.info(
                "Campanha Google Ads criada com sucesso. customer_id=%s campaign_id=%s campaign_resource_name=%s",
                customer_id_limpo,
                campaign_id,
                campaign_resource_name,
            )
            return True, campaign_id
        except GoogleAdsException:
            logger.exception(
                "Falha GoogleAdsException ao criar campanha de pesquisa. customer_id=%s",
                customer_id_limpo,
            )
            return False, None
        except Exception:
            logger.exception(
                "Falha inesperada ao criar campanha de pesquisa. customer_id=%s",
                customer_id_limpo,
            )
            return False, None

    async def vincular_assets(
        self,
        customer_id: str,
        campaign_resource_name: str,
        assets_adicionais: dict,
        credentials_dict: dict,
    ):
        try:
            client = self._build_google_client(credentials_dict)
            asset_service = client.get_service("AssetService")
            campaign_asset_service = client.get_service("CampaignAssetService")

            asset_resource_names: list[tuple[str, Any]] = []

            for sitelink in assets_adicionais.get("sitelinks", []) or []:
                op = client.get_type("AssetOperation")
                op.create.name = f"sitelink-{sitelink.get('texto', 'asset')}"
                op.create.final_urls.append("https://example.com")
                op.create.sitelink_asset.link_text = self._aparar_texto(str(sitelink.get("texto", "")), 25)
                op.create.sitelink_asset.description1 = self._aparar_texto(str(sitelink.get("descricao_1", "")), 35)
                op.create.sitelink_asset.description2 = self._aparar_texto(str(sitelink.get("descricao_2", "")), 35)
                res = asset_service.mutate_assets(customer_id=customer_id, operations=[op])
                asset_resource_names.append((res.results[0].resource_name, client.enums.AssetFieldTypeEnum.SITELINK))

            for callout in assets_adicionais.get("callouts", []) or []:
                op = client.get_type("AssetOperation")
                op.create.name = f"callout-{str(callout)[:20]}"
                op.create.callout_asset.callout_text = self._aparar_texto(str(callout), 25)
                res = asset_service.mutate_assets(customer_id=customer_id, operations=[op])
                asset_resource_names.append((res.results[0].resource_name, client.enums.AssetFieldTypeEnum.CALLOUT))

            for resource_name, field_type in asset_resource_names:
                camp_asset_op = client.get_type("CampaignAssetOperation")
                camp_asset_op.create.asset = resource_name
                camp_asset_op.create.campaign = campaign_resource_name
                camp_asset_op.create.field_type = field_type
                campaign_asset_service.mutate_campaign_assets(
                    customer_id=customer_id,
                    operations=[camp_asset_op],
                )

            logger.info(
                "Assets vinculados com sucesso a campanha %s. total_assets=%s",
                campaign_resource_name,
                len(asset_resource_names),
            )
            return True
        except Exception:
            logger.exception(
                "Falha ao vincular assets na campanha %s.",
                campaign_resource_name,
            )
            return False

    async def pausar_campanha(
        self,
        customer_id: str,
        plataforma_campanha_id: str,
        credentials_dict: dict,
    ):
        logger.info(
            "Mock de pausa Google Ads iniciado. customer_id=%s plataforma_campanha_id=%s credenciais=%s",
            customer_id,
            plataforma_campanha_id,
            list((credentials_dict or {}).keys()),
        )

        # Fluxo real sera implementado com CampaignOperation + CampaignService
        # usando update via FieldMask para alterar o status para PAUSED.
        await asyncio.sleep(1)

        logger.info(
            "Mock de pausa Google Ads finalizado com sucesso. customer_id=%s plataforma_campanha_id=%s",
            customer_id,
            plataforma_campanha_id,
        )
        return True

    async def atualizar_orcamento_diario(
        self,
        customer_id: str,
        plataforma_campanha_id: str,
        novo_valor: float,
        credentials_dict: dict,
    ):
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        campanha_id_limpo = (plataforma_campanha_id or "").strip()

        try:
            google_ads_config = dict(credentials_dict or {})
            use_client_customer_id = google_ads_config.pop("use_client_customer_id", None)
            if use_client_customer_id:
                google_ads_config["login_customer_id"] = str(use_client_customer_id).replace("-", "").strip()

            client = GoogleAdsClient.load_from_dict(google_ads_config)
            googleads_service = client.get_service("GoogleAdsService")
            campaign_budget_service = client.get_service("CampaignBudgetService")

            query = (
                "SELECT campaign.campaign_budget "
                f"FROM campaign WHERE campaign.id = {campanha_id_limpo}"
            )
            response = googleads_service.search(customer_id=customer_id_limpo, query=query)

            budget_resource_name = None
            for row in response:
                budget_resource_name = row.campaign.campaign_budget
                break

            if not budget_resource_name:
                raise ValueError("Nao foi possivel localizar o resource name do orcamento da campanha.")

            budget_operation = client.get_type("CampaignBudgetOperation")
            budget_operation.update.resource_name = budget_resource_name
            budget_operation.update.amount_micros = int(novo_valor * 1000000)
            client.copy_from(
                budget_operation.update_mask,
                protobuf_helpers.field_mask(None, budget_operation.update._pb),
            )

            campaign_budget_service.mutate_campaign_budgets(
                customer_id=customer_id_limpo,
                operations=[budget_operation],
            )

            logger.info(
                "Orcamento Google Ads atualizado com sucesso. customer_id=%s plataforma_campanha_id=%s novo_valor=%.2f",
                customer_id_limpo,
                campanha_id_limpo,
                novo_valor,
            )
            return True
        except GoogleAdsException:
            logger.exception(
                "Falha GoogleAdsException ao atualizar orcamento Google Ads. customer_id=%s plataforma_campanha_id=%s",
                customer_id_limpo,
                campanha_id_limpo,
            )
            return False
        except Exception:
            logger.exception(
                "Falha inesperada ao atualizar orcamento Google Ads. customer_id=%s plataforma_campanha_id=%s",
                customer_id_limpo,
                campanha_id_limpo,
            )
            return False

    async def atualizar_status_adgroup(
        self,
        customer_id: str,
        ad_group_id: str,
        status: str,
        credentials_dict: dict,
    ) -> bool:
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        ad_group_id_limpo = (ad_group_id or "").strip()
        status_norm = (status or "").strip().upper()
        try:
            client = self._build_google_client(credentials_dict)
            ad_group_service = client.get_service("AdGroupService")
            ad_group_operation = client.get_type("AdGroupOperation")
            ad_group = ad_group_operation.update
            ad_group.resource_name = ad_group_service.ad_group_path(customer_id_limpo, ad_group_id_limpo)
            ad_group.status = (
                client.enums.AdGroupStatusEnum.PAUSED
                if status_norm == "PAUSED"
                else client.enums.AdGroupStatusEnum.ENABLED
            )
            client.copy_from(
                ad_group_operation.update_mask,
                protobuf_helpers.field_mask(None, ad_group._pb),
            )
            ad_group_service.mutate_ad_groups(
                customer_id=customer_id_limpo,
                operations=[ad_group_operation],
            )
            logger.info(
                "Status do ad group atualizado. customer_id=%s ad_group_id=%s status=%s",
                customer_id_limpo,
                ad_group_id_limpo,
                status_norm,
            )
            return True
        except Exception:
            logger.exception(
                "Falha ao atualizar status do ad group. customer_id=%s ad_group_id=%s status=%s",
                customer_id_limpo,
                ad_group_id_limpo,
                status_norm,
            )
            return False

    async def atualizar_orcamento_campanha(
        self,
        customer_id: str,
        campaign_id: str,
        novo_valor: float,
        credentials_dict: dict,
    ) -> bool:
        return await self.atualizar_orcamento_diario(
            customer_id=customer_id,
            plataforma_campanha_id=campaign_id,
            novo_valor=novo_valor,
            credentials_dict=credentials_dict,
        )

    async def negativar_termos_adgroup(
        self,
        customer_id: str,
        ad_group_id: str,
        lista_termos: list[str],
        credentials_dict: dict,
    ) -> dict[str, Any]:
        customer_id_limpo = (customer_id or "").replace("-", "").strip()
        ad_group_id_limpo = (ad_group_id or "").strip()
        termos = [str(item or "").strip() for item in (lista_termos or []) if str(item or "").strip()]
        if not termos:
            return {"sucesso": True, "negativados": [], "falhas": []}

        try:
            client = self._build_google_client(credentials_dict)
            ad_group_criterion_service = client.get_service("AdGroupCriterionService")
            ad_group_path = client.get_service("AdGroupService").ad_group_path(customer_id_limpo, ad_group_id_limpo)
            operations = []
            for termo in termos:
                op = client.get_type("AdGroupCriterionOperation")
                criterion = op.create
                criterion.ad_group = ad_group_path
                criterion.negative = True
                criterion.keyword.text = termo
                criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE
                operations.append(op)

            ad_group_criterion_service.mutate_ad_group_criteria(
                customer_id=customer_id_limpo,
                operations=operations,
            )
            logger.info(
                "Termos negativados no adgroup. customer_id=%s ad_group_id=%s total=%s",
                customer_id_limpo,
                ad_group_id_limpo,
                len(termos),
            )
            return {"sucesso": True, "negativados": termos, "falhas": []}
        except Exception:
            logger.exception(
                "Falha ao negativar termos no adgroup. customer_id=%s ad_group_id=%s",
                customer_id_limpo,
                ad_group_id_limpo,
            )
            return {"sucesso": False, "negativados": [], "falhas": termos}
