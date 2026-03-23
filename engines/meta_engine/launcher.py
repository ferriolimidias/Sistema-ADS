import json
import logging
import time
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adcreative import AdCreative
from facebook_business.adobjects.adimage import AdImage
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.campaign import Campaign
from facebook_business.exceptions import FacebookRequestError
from engines.google_engine.geocoder import obter_coordenadas

logger = logging.getLogger(__name__)


class MetaAdsLauncher:
    @staticmethod
    def _normalizar_texto(valor: str | None) -> str:
        return str(valor or "").strip()

    @staticmethod
    def _slugify(valor: str) -> str:
        texto = unicodedata.normalize("NFKD", str(valor or ""))
        texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
        texto = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")
        return texto or "servico"

    def _montar_payload_preview(self, campanha, lista_midias, configuracoes, coordenadas) -> dict:
        meta_ad_account_id = (configuracoes or {}).get("meta_ad_account_id")
        meta_access_token = (configuracoes or {}).get("meta_access_token")
        if not meta_ad_account_id:
            raise ValueError("meta_ad_account_id nao informado para criacao de campanha META.")
        if not meta_access_token:
            raise ValueError("meta_access_token nao informado para criacao de campanha META.")
        if not coordenadas:
            raise ValueError("Coordenadas nao disponiveis para segmentacao local da META.")

        conjuntos = (getattr(campanha, "copy_gerada", {}) or {}).get("conjuntos_anuncios", [])
        if not conjuntos:
            raise ValueError("copy_gerada sem conjuntos_anuncios para criativos da META.")

        campaign_payload = {
            "ad_account_id": meta_ad_account_id,
            "name": f"Meta - Local - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            "objective": "OUTCOME_LEADS",
            "special_ad_categories": ["NONE"],
            "status": "PAUSED",
        }

        budget_cents = int(float(getattr(campanha, "orcamento_diario", 0.0) or 0.0) * 100)
        radius_km = int(getattr(campanha, "raio_geografico", 10) or 10)
        adset_payload = {
            "name": f"AdSet Local - Campanha {campanha.id}",
            "daily_budget": budget_cents,
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "LEAD_GENERATION",
            "targeting": {
                "geo_locations": {
                    "custom_locations": [
                        {
                            "latitude": float(coordenadas[0]),
                            "longitude": float(coordenadas[1]),
                            "radius": radius_km,
                            "distance_unit": "kilometer",
                        }
                    ]
                }
            },
        }

        creatives = []
        for idx, conjunto in enumerate(conjuntos):
            texto_principal = self._normalizar_texto((conjunto.get("texto_principal") or [""])[0])
            titulo = self._normalizar_texto((conjunto.get("titulo") or [""])[0])
            descricao = self._normalizar_texto((conjunto.get("descricao") or [""])[0])
            nome_publico = self._normalizar_texto(conjunto.get("nome_publico")) or f"Publico {idx + 1}"
            nome_servico = self._normalizar_texto(conjunto.get("nome_servico")) or nome_publico
            if not texto_principal or not titulo:
                raise ValueError(f"Conjunto {idx} sem texto_principal/titulo validos para criativo META.")

            creatives.append(
                {
                    "nome_publico": nome_publico,
                    "nome_servico": nome_servico,
                    "message": texto_principal,
                    "title": titulo,
                    "description": descricao,
                    "midias_relacionadas": [
                        item.caminho_arquivo
                        for item in (lista_midias or [])
                        if self._normalizar_texto(getattr(item, "nome_servico", "")).lower()
                        == nome_publico.lower()
                    ],
                }
            )

        creative_payload = {
            "ad_creatives": creatives,
            "fallback_midias_gerais": [
                item.caminho_arquivo for item in (lista_midias or []) if not getattr(item, "nome_servico", None)
            ],
        }

        return {
            "campaign_payload": campaign_payload,
            "adset_payload": adset_payload,
            "creative_payload": creative_payload,
        }

    @staticmethod
    def _selecionar_midia_para_conjunto(lista_midias: list, nome_publico: str):
        if not lista_midias:
            return None
        alvo = str(nome_publico or "").strip().lower()
        for item in lista_midias:
            if str(getattr(item, "nome_servico", "") or "").strip().lower() == alvo:
                return item
        for item in lista_midias:
            if not getattr(item, "nome_servico", None):
                return item
        return lista_midias[0]

    async def criar_campanha_meta(
        self,
        campanha,
        lista_midias: list = None,
        configuracoes: dict = None,
        preview_mode: bool = False,
    ) -> tuple[bool, str, dict | None]:
        lista_midias = lista_midias or []
        configuracoes = configuracoes or {}

        try:
            logger.info("Iniciando criacao na Meta para campanha %s", campanha.id)
            logger.info(
                "Contexto Meta: plataforma=%s tipo=%s midias=%s possui_token=%s",
                getattr(campanha, "plataforma", None),
                getattr(campanha, "tipo", None),
                len(lista_midias),
                bool(configuracoes.get("meta_access_token")),
            )

            endereco = getattr(campanha, "endereco_negocio", None)
            maps_api_key = configuracoes.get("Maps_api_key") or configuracoes.get("maps_api_key")
            coordenadas = await obter_coordenadas(endereco=endereco, api_key=maps_api_key)
            if not coordenadas:
                # Fallback nao configurado: aborta para preservar foco local com qualidade.
                raise ValueError(
                    "Nao foi possivel geocodificar o endereco da campanha META. "
                    "Configure um fallback de cidade ou revise endereco/API key."
                )

            payload_preview = self._montar_payload_preview(
                campanha=campanha,
                lista_midias=lista_midias,
                configuracoes=configuracoes,
                coordenadas=coordenadas,
            )
            logger.info("META PAYLOAD PREVIEW: %s", json.dumps(payload_preview, ensure_ascii=False, indent=2))

            if preview_mode:
                return True, "mock_meta_id_preview_success", payload_preview

            meta_access_token = configuracoes.get("meta_access_token")
            meta_ad_account_id = configuracoes.get("meta_ad_account_id")
            meta_page_id = configuracoes.get("meta_page_id")
            if not meta_page_id:
                raise ValueError("meta_page_id nao informado para criar AdCreative da META.")

            FacebookAdsApi.init(access_token=meta_access_token)
            account = AdAccount(f"act_{meta_ad_account_id}")

            campaign_payload = payload_preview["campaign_payload"]
            adset_payload_base = payload_preview["adset_payload"]
            creatives_payload = payload_preview["creative_payload"]["ad_creatives"]
            public_base_url = str(configuracoes.get("public_base_url") or "https://seu-dominio.com").rstrip("/")

            campaign_obj = Campaign(parent_id=account.get_id_assured())
            campaign_obj[Campaign.Field.name] = campaign_payload["name"]
            campaign_obj[Campaign.Field.objective] = campaign_payload["objective"]
            campaign_obj[Campaign.Field.special_ad_categories] = campaign_payload["special_ad_categories"]
            campaign_obj[Campaign.Field.status] = campaign_payload.get("status", "PAUSED")
            campaign_obj.api_create()
            campaign_id = campaign_obj[Campaign.Field.id]

            for idx, creative_item in enumerate(creatives_payload):
                nome_publico = creative_item.get("nome_publico") or f"Publico {idx + 1}"

                adset_obj = AdSet(parent_id=account.get_id_assured())
                adset_obj[AdSet.Field.campaign_id] = campaign_id
                adset_obj[AdSet.Field.name] = f"{adset_payload_base['name']} - {nome_publico}"
                adset_obj[AdSet.Field.daily_budget] = adset_payload_base["daily_budget"]
                adset_obj[AdSet.Field.billing_event] = adset_payload_base["billing_event"]
                adset_obj[AdSet.Field.optimization_goal] = adset_payload_base["optimization_goal"]
                adset_obj[AdSet.Field.targeting] = adset_payload_base["targeting"]
                adset_obj[AdSet.Field.status] = "PAUSED"
                adset_obj[AdSet.Field.promoted_object] = {"page_id": str(meta_page_id)}
                adset_obj.api_create()
                adset_id = adset_obj[AdSet.Field.id]

                midia = self._selecionar_midia_para_conjunto(lista_midias, nome_publico)
                if not midia:
                    raise ValueError(f"Nenhuma midia encontrada para o conjunto '{nome_publico}'.")

                caminho_arquivo = Path(str(getattr(midia, "caminho_arquivo", "") or ""))
                if not caminho_arquivo.exists():
                    raise FileNotFoundError(f"Arquivo de midia nao encontrado: {caminho_arquivo}")

                image = AdImage(parent_id=account.get_id_assured())
                image[AdImage.Field.filename] = str(caminho_arquivo)
                image.api_create()
                image_hash = image[AdImage.Field.hash]

                creative_obj = AdCreative(parent_id=account.get_id_assured())
                creative_obj[AdCreative.Field.name] = f"Criativo - {nome_publico} - {campanha.id}"
                nome_servico_slug = self._slugify(
                    creative_item.get("nome_servico") or creative_item.get("nome_publico") or nome_publico
                )
                destination_link = f"{public_base_url}/oferta/{campanha.id}/{nome_servico_slug}"
                creative_obj[AdCreative.Field.object_story_spec] = {
                    "page_id": str(meta_page_id),
                    "link_data": {
                        "message": creative_item.get("message", ""),
                        "name": creative_item.get("title", ""),
                        "description": creative_item.get("description", ""),
                        "link": destination_link,
                        "image_hash": image_hash,
                    },
                }
                creative_obj.api_create()
                creative_id = creative_obj[AdCreative.Field.id]

                ad_obj = Ad(parent_id=account.get_id_assured())
                ad_obj[Ad.Field.name] = f"Ad - {nome_publico} - {campanha.id}"
                ad_obj[Ad.Field.adset_id] = adset_id
                ad_obj[Ad.Field.creative] = {"creative_id": creative_id}
                ad_obj[Ad.Field.status] = "PAUSED"
                ad_obj.api_create()

            return True, campaign_id, None
        except FacebookRequestError as exc:
            logger.exception(
                "Erro Meta Graph API (campaign_id_local=%s): code=%s message=%s",
                getattr(campanha, "id", None),
                getattr(exc, "api_error_code", lambda: None)(),
                getattr(exc, "api_error_message", lambda: str(exc))(),
            )
            return False, "", None
        except Exception:
            logger.exception("Falha ao montar payload preview META para campanha_id=%s", getattr(campanha, "id", None))
            return False, "", None

    def pausar_campanha(self, plataforma_campanha_id: str, credentials_dict: dict):
        try:
            token = (credentials_dict or {}).get("meta_bm_token")
            if not token:
                raise ValueError("Token Meta nao informado para pausar campanha.")

            logger.info(
                "Mock de pausa Meta iniciado. plataforma_campanha_id=%s",
                plataforma_campanha_id,
            )

            # Fluxo real a ser habilitado apos validacao em ambiente seguro:
            # from facebook_business.api import FacebookAdsApi
            # FacebookAdsApi.init(access_token=token)
            # campaign = Campaign(plataforma_campanha_id)
            # campaign.api_update(fields=[], params={"status": "PAUSED"})

            # Mantido como mock seguro para evitar pausas reais durante testes locais.
            _campaign = Campaign(plataforma_campanha_id)
            _ = _campaign
            time.sleep(1)

            logger.info(
                "Mock de pausa Meta finalizado com sucesso. plataforma_campanha_id=%s",
                plataforma_campanha_id,
            )
            return True
        except Exception:
            logger.exception(
                "Falha ao pausar campanha Meta. plataforma_campanha_id=%s",
                plataforma_campanha_id,
            )
            return False

    async def atualizar_orcamento_diario(
        self,
        plataforma_campanha_id: str,
        novo_valor: float,
        credentials_dict: dict,
    ):
        try:
            token = (credentials_dict or {}).get("meta_bm_token")
            if not token:
                raise ValueError("Token Meta nao informado para atualizar orcamento.")

            FacebookAdsApi.init(access_token=token)

            campaign = Campaign(plataforma_campanha_id)
            daily_budget_cents = int(novo_valor * 100)
            campaign.api_update(params={"daily_budget": daily_budget_cents})

            logger.info(
                "Orcamento Meta atualizado com sucesso. plataforma_campanha_id=%s novo_valor=%.2f centavos=%s",
                plataforma_campanha_id,
                novo_valor,
                daily_budget_cents,
            )
            return True
        except Exception:
            logger.exception(
                "Falha ao atualizar orcamento da campanha Meta. plataforma_campanha_id=%s novo_valor=%.2f",
                plataforma_campanha_id,
                novo_valor,
            )
            return False

    def localizar_adset_por_nome(
        self,
        plataforma_campanha_id: str,
        nome_servico: str,
        credentials_dict: dict,
    ) -> dict | None:
        try:
            token = (credentials_dict or {}).get("meta_bm_token")
            if not token:
                raise ValueError("Token Meta nao informado para localizar ad set.")
            FacebookAdsApi.init(access_token=token)
            campaign = Campaign(plataforma_campanha_id)
            adsets = campaign.get_ad_sets(
                fields=[
                    AdSet.Field.id,
                    AdSet.Field.name,
                    AdSet.Field.status,
                    AdSet.Field.daily_budget,
                ],
                params={"limit": 200},
            )
            nome_alvo = str(nome_servico or "").strip().lower()
            candidatos = []
            for adset in adsets or []:
                nome = str(adset.get("name") or "")
                if nome_alvo in nome.lower():
                    candidatos.append(
                        {
                            "adset_id": str(adset.get("id")),
                            "adset_name": nome,
                            "status_atual": str(adset.get("status") or ""),
                            "daily_budget": float(adset.get("daily_budget", 0) or 0) / 100.0,
                        }
                    )
            if not candidatos:
                return None
            candidatos.sort(key=lambda item: len(item.get("adset_name", "")))
            return candidatos[0]
        except Exception:
            logger.exception(
                "Falha ao localizar adset por nome. campanha_id=%s nome_servico=%s",
                plataforma_campanha_id,
                nome_servico,
            )
            return None

    async def atualizar_status_adset(
        self,
        adset_id: str,
        status: str,
        credentials_dict: dict,
    ) -> bool:
        try:
            token = (credentials_dict or {}).get("meta_bm_token")
            if not token:
                raise ValueError("Token Meta nao informado para atualizar status do adset.")
            FacebookAdsApi.init(access_token=token)
            status_norm = (status or "").strip().upper()
            status_meta = "PAUSED" if status_norm == "PAUSED" else "ACTIVE"
            adset = AdSet(adset_id)
            adset.api_update(params={"status": status_meta})
            logger.info("Status do adset atualizado. adset_id=%s status=%s", adset_id, status_meta)
            return True
        except Exception:
            logger.exception("Falha ao atualizar status do adset. adset_id=%s", adset_id)
            return False

    async def atualizar_orcamento_adset(
        self,
        adset_id: str,
        novo_valor: float,
        credentials_dict: dict,
    ) -> bool:
        try:
            token = (credentials_dict or {}).get("meta_bm_token")
            if not token:
                raise ValueError("Token Meta nao informado para atualizar orcamento do adset.")
            FacebookAdsApi.init(access_token=token)
            adset = AdSet(adset_id)
            adset.api_update(params={"daily_budget": int(float(novo_valor) * 100)})
            logger.info("Orcamento do adset atualizado. adset_id=%s novo_valor=%.2f", adset_id, novo_valor)
            return True
        except Exception:
            logger.exception(
                "Falha ao atualizar orcamento do adset. adset_id=%s novo_valor=%.2f",
                adset_id,
                novo_valor,
            )
            return False
