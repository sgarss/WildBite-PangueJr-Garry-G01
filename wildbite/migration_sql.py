from django.db import migrations


# Django can't set ON DELETE in PostgreSQL, so replace the foreign key with one that does
def set_on_delete(table, column, ref_table, ref_column, action):
    name = f"{table}_{column}_fkey"
    drop_old = f"""
        DO $$
        DECLARE old_name text;
        BEGIN
            SELECT con.conname INTO old_name
            FROM pg_constraint con
            JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
            WHERE con.conrelid = '{table}'::regclass AND con.contype = 'f' AND att.attname = '{column}';
            EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', old_name);
        END $$;
    """
    add = (
        f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({column}) "
        f"REFERENCES {ref_table} ({ref_column}) ON DELETE {action};"
    )
    add_default = (
        f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({column}) "
        f"REFERENCES {ref_table} ({ref_column}) DEFERRABLE INITIALLY DEFERRED;"
    )
    return migrations.RunSQL(
        sql=[drop_old, add],
        reverse_sql=[f"ALTER TABLE {table} DROP CONSTRAINT {name};", add_default],
    )
