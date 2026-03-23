from sqlalchemy import text

from models.database import engine


def main() -> None:
    print("[migration] Verificando coluna needs_password_change em Usuarios...")

    check_column_sql = text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'Usuarios'
          AND column_name = 'needs_password_change'
        LIMIT 1
        """
    )
    add_column_sql = text(
        'ALTER TABLE "Usuarios" ADD COLUMN needs_password_change BOOLEAN NOT NULL DEFAULT FALSE'
    )
    set_default_sql = text(
        'ALTER TABLE "Usuarios" ALTER COLUMN needs_password_change SET DEFAULT TRUE'
    )

    with engine.begin() as connection:
        column_exists = connection.execute(check_column_sql).scalar() is not None
        if column_exists:
            print("[migration] Coluna needs_password_change ja existe. Nenhuma alteracao aplicada.")
            return

        connection.execute(add_column_sql)
        connection.execute(set_default_sql)
        print("[migration] Coluna needs_password_change adicionada com sucesso.")
        print("[migration] Usuarios existentes permanecem com FALSE; novos usuarios terao TRUE por padrao.")


if __name__ == "__main__":
    main()
