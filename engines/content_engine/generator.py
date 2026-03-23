import json
import logging
from typing import Any

from api.utils.ai_config import MODEL_STRATEGY
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ContentGenerator:
    def __init__(self, openai_api_key: str):
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY nao informada para o ContentGenerator.")
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.model_strategy = MODEL_STRATEGY

    @classmethod
    def from_ferrioli_config(cls, ferrioli_config: Any):
        return cls(openai_api_key=ferrioli_config.openai_api_key)

    @staticmethod
    def _validar_copy_google(data: dict):
        grupos_anuncios = data.get("grupos_anuncios", [])
        sitelinks = data.get("sitelinks", [])
        callouts = data.get("callouts", [])

        if not isinstance(grupos_anuncios, list) or not (2 <= len(grupos_anuncios) <= 4):
            raise ValueError("Quantidade invalida de grupos_anuncios retornada pela OpenAI.")
        if len(sitelinks) != 4 or len(callouts) != 4:
            raise ValueError("Quantidade invalida de sitelinks/callouts retornada pela OpenAI.")
        if any((not isinstance(item, str)) or len(item) > 25 for item in callouts):
            raise ValueError("Um ou mais callouts sao invalidos ou excederam 25 caracteres.")

        for idx, sitelink in enumerate(sitelinks):
            if not isinstance(sitelink, dict):
                raise ValueError(f"Sitelink {idx} invalido: esperado objeto.")
            texto = (sitelink.get("texto") or "").strip()
            descricao_1 = (sitelink.get("descricao_1") or "").strip()
            descricao_2 = (sitelink.get("descricao_2") or "").strip()
            if not texto or len(texto) > 25:
                raise ValueError(f"Sitelink {idx} com texto invalido (max 25).")
            if not descricao_1 or len(descricao_1) > 35:
                raise ValueError(f"Sitelink {idx} com descricao_1 invalida (max 35).")
            if not descricao_2 or len(descricao_2) > 35:
                raise ValueError(f"Sitelink {idx} com descricao_2 invalida (max 35).")
            sitelink["texto"] = texto
            sitelink["descricao_1"] = descricao_1
            sitelink["descricao_2"] = descricao_2

        for idx, grupo in enumerate(grupos_anuncios):
            if not isinstance(grupo, dict):
                raise ValueError(f"Grupo {idx} invalido: esperado objeto.")
            nome_grupo = str(grupo.get("nome_servico", "")).strip()
            palavras_chave = grupo.get("palavras_chave", [])
            headlines = grupo.get("headlines", [])
            descriptions = grupo.get("descriptions", [])
            url_destino = str(grupo.get("url_destino", "") or "").strip()

            if not nome_grupo:
                raise ValueError(f"Grupo {idx} sem nome_servico.")
            if not isinstance(palavras_chave, list) or len(palavras_chave) < 8:
                raise ValueError(f"Grupo {idx} sem palavras_chave suficientes.")
            if len(headlines) != 15 or len(descriptions) != 4:
                raise ValueError(f"Grupo {idx} com quantidade invalida de headlines/descriptions.")
            if any((not isinstance(item, str)) or len(item) > 30 for item in headlines):
                raise ValueError(f"Grupo {idx} com headline invalida (max 30).")
            if any((not isinstance(item, str)) or len(item) > 90 for item in descriptions):
                raise ValueError(f"Grupo {idx} com description invalida (max 90).")
            if any((not isinstance(item, str)) or not str(item).strip() for item in palavras_chave):
                raise ValueError(f"Grupo {idx} com palavra_chave invalida.")

            grupo["nome_servico"] = nome_grupo
            grupo["palavras_chave"] = [str(item).strip() for item in palavras_chave]
            grupo["headlines"] = [str(item).strip() for item in headlines]
            grupo["descriptions"] = [str(item).strip() for item in descriptions]
            if url_destino:
                grupo["url_destino"] = url_destino

    @staticmethod
    def _validar_copy_meta(data: dict):
        conjuntos = data.get("conjuntos_anuncios", [])
        if not isinstance(conjuntos, list) or not conjuntos:
            raise ValueError("Estrutura META invalida: conjuntos_anuncios vazio ou ausente.")

        for idx, conjunto in enumerate(conjuntos):
            if not isinstance(conjunto, dict):
                raise ValueError(f"Conjunto {idx} invalido: esperado objeto.")
            nome_publico = str(conjunto.get("nome_publico", "")).strip()
            texto_principal = conjunto.get("texto_principal", [])
            titulo = conjunto.get("titulo", [])
            descricao = conjunto.get("descricao", [])
            url_destino = str(conjunto.get("url_destino", "") or "").strip()

            if not nome_publico:
                raise ValueError(f"Conjunto {idx} sem nome_publico.")
            if not isinstance(texto_principal, list) or not (1 <= len(texto_principal) <= 3):
                raise ValueError(f"Conjunto {idx} com texto_principal invalido.")
            if not isinstance(titulo, list) or not (1 <= len(titulo) <= 3):
                raise ValueError(f"Conjunto {idx} com titulo invalido.")
            if not isinstance(descricao, list) or not (1 <= len(descricao) <= 2):
                raise ValueError(f"Conjunto {idx} com descricao invalida.")

            conjunto["nome_publico"] = nome_publico
            conjunto["texto_principal"] = [str(item).strip() for item in texto_principal if str(item).strip()]
            conjunto["titulo"] = [str(item).strip() for item in titulo if str(item).strip()]
            conjunto["descricao"] = [str(item).strip() for item in descricao if str(item).strip()]
            if url_destino:
                conjunto["url_destino"] = url_destino

            if not conjunto["texto_principal"] or not conjunto["titulo"] or not conjunto["descricao"]:
                raise ValueError(f"Conjunto {idx} com campos textuais vazios apos sanitizacao.")

    @staticmethod
    def _estimar_tokens_por_texto(texto: str) -> int:
        return max(1, int(len(str(texto or "")) / 4))

    def _log_modelo_e_tokens(self, task: str, response: Any, payload_referencia: str) -> None:
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        total_tokens = getattr(usage, "total_tokens", None) if usage else None
        if total_tokens is None:
            prompt_est = self._estimar_tokens_por_texto(payload_referencia)
            completion_est = 350
            total_est = prompt_est + completion_est
            logger.info(
                "[AI][%s] modelo=%s tokens_estimados=%s (prompt~%s completion~%s)",
                task,
                self.model_strategy,
                total_est,
                prompt_est,
                completion_est,
            )
            return
        logger.info(
            "[AI][%s] modelo=%s tokens=%s (prompt=%s completion=%s)",
            task,
            self.model_strategy,
            total_tokens,
            prompt_tokens,
            completion_tokens,
        )

    async def gerar_copy_campanha(self, nome_servico: str, detalhes_empresa: str, plataforma: str = "GOOGLE"):
        plataforma_norm = (plataforma or "GOOGLE").upper()

        if plataforma_norm == "META":
            prompt = f"""
Voce e um copywriter senior de Meta Ads (Facebook/Instagram), focado em resposta direta.

Gere exclusivamente um JSON valido com esta estrutura:
{{
  "conjuntos_anuncios": [
    {{
      "nome_publico": "...",
      "texto_principal": ["...", "..."],
      "titulo": ["...", "..."],
      "descricao": ["...", "..."]
    }}
  ],
  "sitelinks": [],
  "callouts": []
}}

Regras obrigatorias:
- Retorne de 2 a 4 itens em "conjuntos_anuncios".
- Cada "nome_publico" deve refletir um angulo/servico especifico.
- "texto_principal": de 1 a 3 opcoes persuasivas (pode usar emojis com moderacao).
- "titulo": de 1 a 3 opcoes curtas e chamativas.
- "descricao": de 1 a 2 opcoes curtas de apoio.
- Linguagem em portugues do Brasil.
- Nao inclua explicacoes fora do JSON.

Servico: {nome_servico}
Detalhes da empresa: {detalhes_empresa}
""".strip()
        else:
            prompt = f"""
Voce e um copywriter senior de Google Ads focado em resposta direta e estrutura STAG.

Gere exclusivamente um JSON valido com esta estrutura:
{{
  "grupos_anuncios": [
    {{
      "nome_servico": "...",
      "palavras_chave": ["...", "..."],
      "headlines": ["...", "..."],
      "descriptions": ["...", "..."]
    }}
  ],
  "sitelinks": [
    {{
      "texto": "...",
      "descricao_1": "...",
      "descricao_2": "..."
    }}
  ],
  "callouts": ["...", "..."]
}}

Regras obrigatorias:
- Retorne de 2 a 4 grupos em "grupos_anuncios".
- Cada grupo deve ter "nome_servico" objetivo.
- Cada grupo deve conter no minimo 8 palavras_chave com intencao local.
- Inclua variacoes locais nas palavras_chave (ex: "perto de mim", "em [Cidade]", "na [Cidade]").
- Cada grupo deve ter exatamente 15 headlines (max 30 chars cada).
- Cada grupo deve ter exatamente 4 descriptions (max 90 chars cada).
- Retorne exatamente 4 sitelinks.
- Cada sitelink deve conter: texto (max 25 chars), descricao_1 (max 35 chars), descricao_2 (max 35 chars).
- Retorne exatamente 4 callouts, cada um com no maximo 25 caracteres.
- Linguagem em portugues do Brasil.
- Use gatilhos mentais diretos.
- Foque em intencao de busca.
- Inclua CTAs claros.
- Nao inclua chaves extras.
- Nao inclua explicacoes fora do JSON.

Servico: {nome_servico}
Detalhes da empresa: {detalhes_empresa}
""".strip()

        try:
            response = await self.client.chat.completions.create(
                model=self.model_strategy,
                response_format={"type": "json_object"},
                temperature=0.8,
                messages=[
                    {
                        "role": "system",
                        "content": "Voce gera assets publicitarios em JSON com alta aderencia a limites de caracteres.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            self._log_modelo_e_tokens("gerar_copy_campanha", response, prompt)
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)

            if plataforma_norm == "META":
                self._validar_copy_meta(data)
                logger.info("Copy de Meta Ads gerada com sucesso para servico=%s", nome_servico)
            else:
                self._validar_copy_google(data)
                logger.info("Copy de Google Ads gerada com sucesso para servico=%s", nome_servico)
            return data
        except Exception:
            logger.exception(
                "Falha ao gerar copy de campanha para servico=%s plataforma=%s",
                nome_servico,
                plataforma_norm,
            )
            raise

    async def gerar_copy_google_ads(self, nome_servico: str, detalhes_empresa: str):
        return await self.gerar_copy_campanha(
            nome_servico=nome_servico,
            detalhes_empresa=detalhes_empresa,
            plataforma="GOOGLE",
        )

    async def gerar_landing_page(self, nome_servico: str, copy_gerada: dict):
        prompt = f"""
Voce e um especialista em CRO e landing pages.

Gere um HTML completo e pronto para uso, usando TailwindCSS via CDN.

Requisitos obrigatorios:
- Retorne apenas o HTML completo.
- Pagina limpa, moderna e focada em alta conversao.
- Titulo principal forte e direto.
- Subtitulo persuasivo.
- Secao com exatamente 3 beneficios do servico.
- CTA principal bem destacado.
- Botao flutuante de WhatsApp visivel.
- Linguagem em portugues do Brasil.
- Estruture o HTML com boa hierarquia visual.

Servico: {nome_servico}
Copy gerada: {json.dumps(copy_gerada, ensure_ascii=False)}
""".strip()

        try:
            response = await self.client.chat.completions.create(
                model=self.model_strategy,
                temperature=0.7,
                messages=[
                    {
                        "role": "system",
                        "content": "Voce gera landing pages em HTML completas, limpas e prontas para conversao.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            self._log_modelo_e_tokens("gerar_landing_page", response, prompt)
            html = (response.choices[0].message.content or "").strip()
            if not html.lower().startswith("<!doctype html") and not html.lower().startswith("<html"):
                raise ValueError("A OpenAI nao retornou um HTML completo valido.")

            logger.info("Landing page gerada com sucesso para servico=%s", nome_servico)
            return html
        except Exception:
            logger.exception("Falha ao gerar landing page para servico=%s", nome_servico)
            raise
