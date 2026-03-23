import base64
import mimetypes
import re
from pathlib import Path

import httpx


class EvolutionService:
    @staticmethod
    def _build_base_config(config):
        evolution_api_url = (getattr(config, "evolution_api_url", None) or "").rstrip("/")
        evolution_api_key = getattr(config, "evolution_api_key", None)
        evolution_instance_name = getattr(config, "evolution_instance_name", None)
        if not evolution_api_url:
            raise ValueError("evolution_api_url nao configurado.")
        if not evolution_api_key:
            raise ValueError("evolution_api_key nao configurado.")
        if not evolution_instance_name:
            raise ValueError("evolution_instance_name nao configurado.")
        return evolution_api_url, evolution_api_key, evolution_instance_name

    @staticmethod
    def _post_json(evolution_api_url: str, instance: str, endpoint_path: str, payload: dict, api_key: str):
        endpoint = f"{evolution_api_url}/{endpoint_path}/{instance}"
        headers = {
            "apikey": api_key,
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(endpoint, json=payload, headers=headers)

        try:
            parsed = response.json()
        except Exception:
            parsed = {"raw_response": response.text}

        if response.status_code >= 400:
            raise RuntimeError(
                f"Falha na Evolution API ({response.status_code}) em {endpoint_path}: {parsed}"
            )
        return parsed

    @staticmethod
    def _normalize_number(numero: str) -> str:
        numero_limpo = re.sub(r"\D+", "", str(numero or ""))
        if not numero_limpo:
            raise ValueError("Numero de cliente invalido para criar grupo de onboarding.")
        return numero_limpo

    def enviar_relatorio_pdf(self, config, remote_jid, mensagem, pdf_path, pdf_nome):
        evolution_api_url, evolution_api_key, evolution_instance_name = self._build_base_config(config)
        if not remote_jid:
            raise ValueError("remote_jid nao informado para envio no WhatsApp.")

        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF nao encontrado para envio: {pdf_file}")

        pdf_base64 = base64.b64encode(pdf_file.read_bytes()).decode("utf-8")
        payload = {
            "number": remote_jid,
            "mediaMessage": {
                "mediatype": "document",
                "caption": mensagem,
                "media": f"data:application/pdf;base64,{pdf_base64}",
                "fileName": pdf_nome,
            },
        }
        parsed = self._post_json(
            evolution_api_url=evolution_api_url,
            instance=evolution_instance_name,
            endpoint_path="message/sendMedia",
            payload=payload,
            api_key=evolution_api_key,
        )

        return {
            "status_code": 200,
            "endpoint": f"{evolution_api_url}/message/sendMedia/{evolution_instance_name}",
            "payload_enviado": payload,
            "response": parsed,
        }

    def enviar_texto_whatsapp(self, config, numero_destino, mensagem):
        evolution_api_url, evolution_api_key, evolution_instance_name = self._build_base_config(config)
        numero_limpo = self._normalize_number(numero_destino)
        payload = {
            "number": numero_limpo,
            "textMessage": {
                "text": mensagem,
            },
        }
        parsed = self._post_json(
            evolution_api_url=evolution_api_url,
            instance=evolution_instance_name,
            endpoint_path="message/sendText",
            payload=payload,
            api_key=evolution_api_key,
        )
        return {
            "status_code": 200,
            "endpoint": f"{evolution_api_url}/message/sendText/{evolution_instance_name}",
            "payload_enviado": payload,
            "response": parsed,
        }

    def criar_grupo_onboarding(
        self,
        config,
        nome_empresa,
        numero_cliente,
        logo_url=None,
        plataforma="Google Ads e Meta Ads",
        url_dashboard="https://seu-dominio.com/admin/dashboard",
        email_login=None,
        senha_temporaria=None,
        url_login="https://seu-dominio.com/login",
    ):
        evolution_api_url, evolution_api_key, evolution_instance_name = self._build_base_config(config)

        numero_limpo = self._normalize_number(numero_cliente)
        participante_jid = f"{numero_limpo}@s.whatsapp.net"
        nome_grupo = f"Anuncios - {str(nome_empresa or 'Cliente').strip()}"

        # Passo A: criar grupo
        create_payload = {
            "subject": nome_grupo,
            "participants": [participante_jid],
        }
        create_response = self._post_json(
            evolution_api_url=evolution_api_url,
            instance=evolution_instance_name,
            endpoint_path="group/create",
            payload=create_payload,
            api_key=evolution_api_key,
        )
        group_id = (
            create_response.get("id")
            or (create_response.get("groupInfo") or {}).get("id")
            or (create_response.get("group") or {}).get("id")
        )
        if not group_id:
            raise RuntimeError(f"Evolution nao retornou ID do grupo: {create_response}")

        # Passo B: descricao
        self._post_json(
            evolution_api_url=evolution_api_url,
            instance=evolution_instance_name,
            endpoint_path="group/updateDescription",
            payload={
                "groupJid": group_id,
                "id": group_id,
                "description": "Grupo oficial de acompanhamento de anuncios - Ferrioli Midias. 🚀",
            },
            api_key=evolution_api_key,
        )

        # Passo C: foto (opcional)
        if logo_url:
            with httpx.Client(timeout=30.0) as client:
                image_response = client.get(logo_url)
            image_response.raise_for_status()
            content_type = image_response.headers.get("content-type") or mimetypes.guess_type(logo_url)[0] or "image/png"
            image_base64 = base64.b64encode(image_response.content).decode("utf-8")
            self._post_json(
                evolution_api_url=evolution_api_url,
                instance=evolution_instance_name,
                endpoint_path="group/updateGroupPicture",
                payload={
                    "groupJid": group_id,
                    "id": group_id,
                    "image": f"data:{content_type};base64,{image_base64}",
                },
                api_key=evolution_api_key,
            )

        # Passo D: boas-vindas
        mensagem_boas_vindas = (
            f"Olá, *{str(nome_empresa or 'Cliente').strip()}*! Seja bem-vindo à sua Sala de Guerra de Anúncios. 📈\n\n"
            "Este é o nosso canal oficial de comunicação. Veja como vamos trabalhar:\n\n"
            "🚀 *O que esperar agora:*\n"
            f"Nas próximas 48h, nossa IA finalizará a estruturação técnica das suas campanhas de {plataforma}.\n\n"
            "📊 *Relatórios de Performance:*\n"
            "Todo fechamento de ciclo, enviaremos aqui o relatório de ROAS (Retorno sobre Investimento) para acompanharmos o lucro real.\n\n"
            "🔐 *Seu Acesso Exclusivo ao Painel:*\n"
            f"Link: {url_login}\n"
            f"Usuário: {email_login or 'Nao informado'}\n"
            f"Senha Temporária: *{senha_temporaria or 'Nao informada'}*\n"
            "_(Recomendamos trocar a senha no primeiro acesso)_\n\n"
            "🔗 *Seu Dashboard:*\n"
            f"Você pode acompanhar os números em tempo real pelo link: {url_dashboard}\n\n"
            "🙏 *Regra de Ouro:*\n"
            "Sempre que realizar uma venda vinda dos anúncios, lembre-se de nos avisar ou registrar no sistema para que nossa IA aprenda o que está trazendo dinheiro de verdade!\n\n"
            "Vamos pra cima! 🏁"
        )
        self._post_json(
            evolution_api_url=evolution_api_url,
            instance=evolution_instance_name,
            endpoint_path="message/sendText",
            payload={
                "number": group_id,
                "textMessage": {
                    "text": mensagem_boas_vindas
                },
            },
            api_key=evolution_api_key,
        )

        return group_id
