"""
data/migrations/run_migration.py
Aplica la migracion 001_unify_schema.sql sobre la BD existente.
Maneja de forma segura los errores 'duplicate column name' (idempotente).

Uso:
    python data/migrations/run_migration.py
"""

import sqlite3
import sys
import os
from pathlib import Path

# Forzar UTF-8 en stdout para Windows (evita UnicodeEncodeError con cp1252)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Añadir raíz al path
sys.path.append(str(Path(__file__).parent.parent.parent))
import config

SQL_FILE = Path(__file__).parent / "001_unify_schema.sql"
DB_PATH  = config.DB_PATH


def run():
    if not os.path.exists(DB_PATH):
        print(f"[WARN] Base de datos no encontrada en: {DB_PATH}")
        print("   Ejecuta primero: python data/migrate_json_to_db.py")
        return

    print(f"[INFO] Aplicando migracion sobre: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    with open(SQL_FILE, "r", encoding="utf-8") as f:
        raw_sql = f.read()

    # Ejecutar sentencia por sentencia para manejar errores idempotentes
    statements = [s.strip() for s in raw_sql.split(";") if s.strip()]
    ok = 0
    skipped = 0
    errors = []

    for stmt in statements:
        # Ignorar comentarios puros
        if stmt.startswith("--") or not stmt:
            continue
        try:
            cursor.execute(stmt)
            ok += 1
        except sqlite3.OperationalError as e:
            msg = str(e)
            # "duplicate column name" es esperado en re-ejecuciones (idempotente)
            if "duplicate column name" in msg or "already exists" in msg:
                skipped += 1
            else:
                errors.append((stmt[:60], msg))
                print(f"   [ERROR] {msg}")
                print(f"      En: {stmt[:80]}...")

    conn.commit()
    conn.close()

    print(f"\n[OK] Migracion completada:")
    print(f"   Sentencias ejecutadas : {ok}")
    print(f"   Columnas ya existentes: {skipped} (OK - idempotente)")
    if errors:
        print(f"   [ERROR] Errores reales: {len(errors)}")
        for stmt_preview, msg in errors:
            print(f"      -> {stmt_preview!r}: {msg}")
    else:
        print("   Sin errores criticos. Migracion exitosa.")


if __name__ == "__main__":
    run()
