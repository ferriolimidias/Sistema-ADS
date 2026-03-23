from sqlalchemy import text

from models.database import engine


def main() -> None:
    print("[migration] Iniciando verificacao da coluna meta_page_id em Ferrioli_Config...")

    check_column_sql = text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'Ferrioli_Config'
          AND column_name = 'meta_page_id'
        LIMIT 1
        """
    )
    alter_table_sql = text('ALTER TABLE "Ferrioli_Config" ADD COLUMN meta_page_id VARCHAR')

    with engine.begin() as connection:
        column_exists = connection.execute(check_column_sql).scalar() is not None
        if column_exists:
            print("[migration] Coluna meta_page_id ja existente. Nenhuma alteracao aplicada.")
            return

        connection.execute(alter_table_sql)
        print("[migration] Coluna meta_page_id adicionada com sucesso.")


if __name__ == "__main__":
    main()
