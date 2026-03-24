from sqlalchemy import text

from models.database import engine


def main() -> None:
    print("[migration] Verificando tabela ConsumoIA...")

    check_table_sql = text(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'ConsumoIA'
        LIMIT 1
        """
    )
    create_table_sql = text(
        """
        CREATE TABLE "ConsumoIA" (
            id SERIAL PRIMARY KEY,
            modelo VARCHAR NOT NULL,
            tarefa VARCHAR NOT NULL,
            tokens_input INTEGER NOT NULL DEFAULT 0,
            tokens_output INTEGER NOT NULL DEFAULT 0,
            custo_estimado FLOAT NOT NULL DEFAULT 0.0,
            timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        )
        """
    )
    idx_modelo = text('CREATE INDEX IF NOT EXISTS ix_ConsumoIA_modelo ON "ConsumoIA"(modelo)')
    idx_tarefa = text('CREATE INDEX IF NOT EXISTS ix_ConsumoIA_tarefa ON "ConsumoIA"(tarefa)')
    idx_timestamp = text('CREATE INDEX IF NOT EXISTS ix_ConsumoIA_timestamp ON "ConsumoIA"(timestamp)')

    with engine.begin() as connection:
        exists = connection.execute(check_table_sql).scalar() is not None
        if not exists:
            connection.execute(create_table_sql)
            print("[migration] Tabela ConsumoIA criada.")
        else:
            print("[migration] Tabela ConsumoIA ja existe.")

        connection.execute(idx_modelo)
        connection.execute(idx_tarefa)
        connection.execute(idx_timestamp)
        print("[migration] Indices de ConsumoIA verificados.")


if __name__ == "__main__":
    main()
