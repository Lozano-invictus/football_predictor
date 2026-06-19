"""
data/add_backtest_table.py
Script para agregar la tabla backtest_results a la base de datos existente.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from data.database import Base, engine
from sqlalchemy import inspect

def main():
    print("Verificando tablas en la base de datos...")
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if "backtest_results" in existing_tables:
        print("La tabla backtest_results ya existe!")
        return

    print("Creando tabla backtest_results...")
    from data.database import BacktestResult
    BacktestResult.__table__.create(bind=engine)

    print("Tabla creada exitosamente!")

if __name__ == "__main__":
    main()
