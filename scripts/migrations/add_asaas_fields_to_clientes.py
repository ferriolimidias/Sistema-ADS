from sqlalchemy import text

from models.database import engine


def main() -> None:
    print("[migration] Verificando campos Asaas em Clientes...")

    add_asaas_customer_sql = text(
        """
        ALTER TABLE "Clientes"
        ADD COLUMN IF NOT EXISTS asaas_customer_id VARCHAR NULL
        """
    )
    add_vencimento_sql = text(
        """
        ALTER TABLE "Clientes"
        ADD COLUMN IF NOT EXISTS data_vencimento_licenca TIMESTAMP WITHOUT TIME ZONE NULL
        """
    )
    idx_asaas_sql = text('CREATE UNIQUE INDEX IF NOT EXISTS ix_Clientes_asaas_customer_id ON "Clientes"(asaas_customer_id)')
    idx_vencimento_sql = text(
        'CREATE INDEX IF NOT EXISTS ix_Clientes_data_vencimento_licenca ON "Clientes"(data_vencimento_licenca)'
    )

    with engine.begin() as connection:
        connection.execute(add_asaas_customer_sql)
        connection.execute(add_vencimento_sql)
        connection.execute(idx_asaas_sql)
        connection.execute(idx_vencimento_sql)
        print("[migration] Campos Asaas em Clientes verificados.")


if __name__ == "__main__":
    main()
