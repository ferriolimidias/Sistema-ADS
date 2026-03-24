import httpx

from models.schema import FerrioliConfig


class CloudflareService:
    def criar_subdominio_cname(self, slug: str, config: FerrioliConfig) -> dict:
        if not config:
            raise ValueError("Configuracao FerrioliConfig nao encontrada.")
        token = str(config.cloudflare_api_token or "").strip()
        zone_id = str(config.cloudflare_zone_id or "").strip()
        cname_target = str(config.cloudflare_cname_target or "").strip()
        if not token or not zone_id or not cname_target:
            raise ValueError("Campos Cloudflare incompletos em FerrioliConfig.")

        slug_limpo = str(slug or "").strip().lower()
        if not slug_limpo:
            raise ValueError("Slug invalido para criacao do subdominio.")

        endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "type": "CNAME",
            "name": slug_limpo,
            "content": cname_target,
            "ttl": 1,
            "proxied": True,
            "comment": "Gerado via Sistema ADS API",
        }

        with httpx.Client(timeout=20.0) as client:
            response = client.post(endpoint, headers=headers, json=payload)
        try:
            parsed = response.json()
        except Exception:
            parsed = {"raw_response": response.text}

        return {
            "status_code": int(response.status_code),
            "payload": parsed,
        }
