
"""
data/init_elo.py
Script para inicializar y reconstruir todo el historial de Elo.
Ejecutar una vez para darle vida al sistema de Elo.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from data.elo_engine import EloEngine
from data.database import init_db
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    print("=" * 60)
    print("INICIALIZACIÓN DEL MOTOR ELO")
    print("=" * 60)

    # Asegurar que la base de datos esté al día
    logger.info("Inicializando base de datos...")
    init_db()
    logger.info("✅ Base de datos inicializada correctamente")

    # Crear motor Elo
    elo_engine = EloEngine()

    # Reconstruir historial
    logger.info("Reconstruyendo historial de Elo desde 2022-23...")
    result = elo_engine.rebuild_all_elo_history(start_season="2022-23")

    print("\n" + "=" * 60)
    print("RESULTADO DE LA INICIALIZACIÓN")
    print("=" * 60)
    print(f"Estado: {result['status']}")

    if result['status'] == 'success':
        print(f"Partidos procesados: {result['processed_matches']}")
        print(f"Errores: {result['errors']}")
        if result['errors'] > 0:
            print("\nDetalles de errores:")
            for err in result['error_details']:
                print(f"- {err}")

        # Obtener top 10 equipos
        print("\n" + "-" * 60)
        print("TOP 10 EQUIPOS POR ELO")
        print("-" * 60)
        top_teams = elo_engine.get_top_teams(10)
        for i, team in enumerate(top_teams, 1):
            print(f"{i:2d}. {team['name']:30s} | {team['elo']:.2f}")

    else:
        print(f"Error: {result['message']}")

    print("=" * 60)


if __name__ == "__main__":
    main()
