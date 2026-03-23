from sqlalchemy import text

from models.database import engine


def main() -> None:
    print("[migration] Verificando tabela AuditLog...")

    check_table_sql = text(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'AuditLog'
        LIMIT 1
        """
    )

    create_table_sql = text(
        """
        CREATE TABLE "AuditLog" (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NULL REFERENCES "Usuarios"(id),
            acao VARCHAR NOT NULL,
            recurso VARCHAR NOT NULL,
            detalhes JSON NULL,
            ip_address VARCHAR NULL,
            timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        )
        """
    )
    create_index_user_sql = text('CREATE INDEX IF NOT EXISTS ix_AuditLog_user_id ON "AuditLog"(user_id)')
    create_index_acao_sql = text('CREATE INDEX IF NOT EXISTS ix_AuditLog_acao ON "AuditLog"(acao)')
    create_index_timestamp_sql = text('CREATE INDEX IF NOT EXISTS ix_AuditLog_timestamp ON "AuditLog"(timestamp)')

    with engine.begin() as connection:
        table_exists = connection.execute(check_table_sql).scalar() is not None
        if not table_exists:
            connection.execute(create_table_sql)
            print("[migration] Tabela AuditLog criada com sucesso.")
        else:
            print("[migration] Tabela AuditLog ja existe.")

        connection.execute(create_index_user_sql)
        connection.execute(create_index_acao_sql)
        connection.execute(create_index_timestamp_sql)
        print("[migration] Indices da AuditLog verificados.")


if __name__ == "__main__":
    main()
