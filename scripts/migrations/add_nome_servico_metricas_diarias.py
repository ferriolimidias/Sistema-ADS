from sqlalchemy import text

from models.database import engine


def main() -> None:
    print("[migration] Verificando coluna nome_servico e constraint de unicidade em MetricasDiarias...")

    check_column_sql = text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'MetricasDiarias'
          AND column_name = 'nome_servico'
        LIMIT 1
        """
    )
    add_column_sql = text('ALTER TABLE "MetricasDiarias" ADD COLUMN nome_servico VARCHAR NULL')

    check_old_constraint_sql = text(
        """
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'MetricasDiarias'
          AND constraint_name = 'uq_metricas_campanha_data'
        LIMIT 1
        """
    )
    drop_old_constraint_sql = text(
        'ALTER TABLE "MetricasDiarias" DROP CONSTRAINT IF EXISTS uq_metricas_campanha_data'
    )
    add_new_constraint_sql = text(
        """
        ALTER TABLE "MetricasDiarias"
        ADD CONSTRAINT uq_metricas_campanha_data_servico
        UNIQUE (campanha_id, data, nome_servico)
        """
    )
    check_new_constraint_sql = text(
        """
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'MetricasDiarias'
          AND constraint_name = 'uq_metricas_campanha_data_servico'
        LIMIT 1
        """
    )
    create_index_sql = text(
        'CREATE INDEX IF NOT EXISTS ix_MetricasDiarias_nome_servico ON "MetricasDiarias"(nome_servico)'
    )

    with engine.begin() as connection:
        has_column = connection.execute(check_column_sql).scalar() is not None
        if not has_column:
            connection.execute(add_column_sql)
            print("[migration] Coluna nome_servico adicionada.")
        else:
            print("[migration] Coluna nome_servico ja existe.")

        has_old_constraint = connection.execute(check_old_constraint_sql).scalar() is not None
        if has_old_constraint:
            connection.execute(drop_old_constraint_sql)
            print("[migration] Constraint antiga uq_metricas_campanha_data removida.")

        has_new_constraint = connection.execute(check_new_constraint_sql).scalar() is not None
        if not has_new_constraint:
            connection.execute(add_new_constraint_sql)
            print("[migration] Constraint nova uq_metricas_campanha_data_servico criada.")
        else:
            print("[migration] Constraint nova uq_metricas_campanha_data_servico ja existe.")

        connection.execute(create_index_sql)
        print("[migration] Indice de nome_servico verificado.")


if __name__ == "__main__":
    main()
