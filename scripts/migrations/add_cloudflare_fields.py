from sqlalchemy import text

from models.database import engine


def main() -> None:
    print("[migration] Verificando campos Cloudflare...")

    add_cf_token = text(
        """
        ALTER TABLE "Ferrioli_Config"
        ADD COLUMN IF NOT EXISTS cloudflare_api_token VARCHAR NULL
        """
    )
    add_cf_zone = text(
        """
        ALTER TABLE "Ferrioli_Config"
        ADD COLUMN IF NOT EXISTS cloudflare_zone_id VARCHAR NULL
        """
    )
    add_cf_target = text(
        """
        ALTER TABLE "Ferrioli_Config"
        ADD COLUMN IF NOT EXISTS cloudflare_cname_target VARCHAR NULL
        """
    )
    add_cliente_domain = text(
        """
        ALTER TABLE "Clientes"
        ADD COLUMN IF NOT EXISTS dominio_personalizado VARCHAR NULL
        """
    )

    with engine.begin() as connection:
        connection.execute(add_cf_token)
        connection.execute(add_cf_zone)
        connection.execute(add_cf_target)
        connection.execute(add_cliente_domain)
        print("[migration] Campos Cloudflare verificados com sucesso.")


if __name__ == "__main__":
    main()
