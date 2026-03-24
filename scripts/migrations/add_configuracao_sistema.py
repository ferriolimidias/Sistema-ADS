from sqlalchemy import text

from models.database import engine


def main() -> None:
    print("[migration] Verificando tabela ConfiguracaoSistema...")

    check_table_sql = text(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'ConfiguracaoSistema'
        LIMIT 1
        """
    )
    create_table_sql = text(
        """
        CREATE TABLE "ConfiguracaoSistema" (
            id INTEGER PRIMARY KEY,
            intraday_cleaner_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            admin_whatsapp_number VARCHAR NULL
        )
        """
    )
    upsert_default_row_sql = text(
        """
        INSERT INTO "ConfiguracaoSistema" (id, intraday_cleaner_enabled, admin_whatsapp_number)
        VALUES (1, FALSE, NULL)
        ON CONFLICT (id) DO NOTHING
        """
    )

    with engine.begin() as connection:
        exists = connection.execute(check_table_sql).scalar() is not None
        if not exists:
            connection.execute(create_table_sql)
            print("[migration] Tabela ConfiguracaoSistema criada.")
        else:
            print("[migration] Tabela ConfiguracaoSistema ja existe.")

        connection.execute(upsert_default_row_sql)
        print("[migration] Singleton id=1 de ConfiguracaoSistema verificado.")


if __name__ == "__main__":
    main()
