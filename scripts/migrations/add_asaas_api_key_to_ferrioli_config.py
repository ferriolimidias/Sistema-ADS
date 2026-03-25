from sqlalchemy import text

from models.database import engine


def main() -> None:
    print("[migration] Verificando coluna asaas_api_key em Ferrioli_Config...")
    add_asaas_api_key = text(
        """
        ALTER TABLE "Ferrioli_Config"
        ADD COLUMN IF NOT EXISTS asaas_api_key VARCHAR NULL
        """
    )
    with engine.begin() as connection:
        connection.execute(add_asaas_api_key)
    print("[migration] Coluna asaas_api_key verificada com sucesso.")


if __name__ == "__main__":
    main()
