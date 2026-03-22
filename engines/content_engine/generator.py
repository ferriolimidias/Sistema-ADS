import json
import logging
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ContentGenerator:
    def __init__(self, openai_api_key: str):
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY nao informada para o ContentGenerator.")
        self.client = AsyncOpenAI(api_key=openai_api_key)

    @classmethod
    def from_ferrioli_config(cls, ferrioli_config: Any):
        return cls(openai_api_key=ferrioli_config.openai_api_key)

    async def gerar_copy_google_ads(self, nome_servico: str, detalhes_empresa: str):
        prompt = f"""
Voce e um copywriter senior de Google Ads focado em resposta direta.

Gere exclusivamente um JSON valido com esta estrutura:
{{
  "headlines": ["...", "..."],
  "descriptions": ["...", "..."]
}}

Regras obrigatorias:
- Retorne exatamente 15 headlines.
- Cada headline deve ter no maximo 30 caracteres.
- Retorne exatamente 4 descriptions.
- Cada description deve ter no maximo 90 caracteres.
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
                model="gpt-4o",
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
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)

            headlines = data.get("headlines", [])
            descriptions = data.get("descriptions", [])

            if len(headlines) != 15 or len(descriptions) != 4:
                raise ValueError("Quantidade invalida de headlines ou descriptions retornada pela OpenAI.")
            if any(len(item) > 30 for item in headlines):
                raise ValueError("Uma ou mais headlines excederam 30 caracteres.")
            if any(len(item) > 90 for item in descriptions):
                raise ValueError("Uma ou mais descriptions excederam 90 caracteres.")

            logger.info("Copy de Google Ads gerada com sucesso para servico=%s", nome_servico)
            return data
        except Exception:
            logger.exception("Falha ao gerar copy de Google Ads para servico=%s", nome_servico)
            raise

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
                model="gpt-4o",
                temperature=0.7,
                messages=[
                    {
                        "role": "system",
                        "content": "Voce gera landing pages em HTML completas, limpas e prontas para conversao.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            html = (response.choices[0].message.content or "").strip()
            if not html.lower().startswith("<!doctype html") and not html.lower().startswith("<html"):
                raise ValueError("A OpenAI nao retornou um HTML completo valido.")

            logger.info("Landing page gerada com sucesso para servico=%s", nome_servico)
            return html
        except Exception:
            logger.exception("Falha ao gerar landing page para servico=%s", nome_servico)
            raise
