from datetime import datetime, timedelta
import re

import httpx


class AsaasService:
    base_url = "https://api.asaas.com/v3"

    @staticmethod
    def _headers(api_key: str) -> dict:
        token = str(api_key or "").strip()
        if not token:
            raise ValueError("api_key do Asaas nao informada.")
        return {
            "access_token": token,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict:
        try:
            parsed = response.json()
        except Exception:
            parsed = {"raw_response": response.text}

        if response.status_code >= 400:
            raise RuntimeError(f"Asaas retornou erro ({response.status_code}): {parsed}")
        return parsed if isinstance(parsed, dict) else {"data": parsed}

    def criar_cliente(
        self,
        api_key: str,
        nome: str,
        cpf_cnpj: str | None = None,
        email: str | None = None,
        telefone: str | None = None,
    ) -> dict:
        nome_limpo = str(nome or "").strip()
        if not nome_limpo:
            raise ValueError("Nome do cliente e obrigatorio para criar cliente no Asaas.")

        payload = {"name": nome_limpo}
        cpf_cnpj_limpo = re.sub(r"\D+", "", str(cpf_cnpj or ""))
        telefone_limpo = re.sub(r"\D+", "", str(telefone or ""))
        if cpf_cnpj_limpo:
            payload["cpfCnpj"] = cpf_cnpj_limpo
        if email:
            payload["email"] = str(email).strip()
        if telefone_limpo:
            payload["mobilePhone"] = telefone_limpo

        endpoint = f"{self.base_url}/customers"
        with httpx.Client(timeout=30.0) as client:
            response = client.post(endpoint, headers=self._headers(api_key), json=payload)
        parsed = self._parse_response(response)
        return {"id": parsed.get("id"), "raw": parsed}

    def criar_cobranca_avulsa(self, api_key, asaas_customer_id, valor, descricao) -> dict:
        customer_id = str(asaas_customer_id or "").strip()
        if not customer_id:
            raise ValueError("asaas_customer_id nao informado.")

        valor_float = float(valor or 0)
        if valor_float <= 0:
            raise ValueError("Valor da cobranca deve ser maior que zero.")

        descricao_limpa = str(descricao or "").strip()
        if not descricao_limpa:
            raise ValueError("Descricao da cobranca nao informada.")

        due_date = (datetime.utcnow() + timedelta(days=1)).date().isoformat()
        payload = {
            "customer": customer_id,
            "billingType": "PIX",
            "value": valor_float,
            "dueDate": due_date,
            "description": descricao_limpa,
        }

        endpoint = f"{self.base_url}/payments"
        with httpx.Client(timeout=30.0) as client:
            response = client.post(endpoint, headers=self._headers(api_key), json=payload)
        parsed = self._parse_response(response)
        return {"invoiceUrl": parsed.get("invoiceUrl"), "id": parsed.get("id"), "raw": parsed}
