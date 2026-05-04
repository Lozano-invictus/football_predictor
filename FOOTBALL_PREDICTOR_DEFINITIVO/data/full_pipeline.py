"""
data/full_pipeline.py
Pipeline ETL integrado para actualización total del sistema.
Gestiona equipos, plantillas, xG y transferencias.
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Añadir raíz al path
sys.path.append(str(Path(__file__).parent.parent))

import config
from data.database import get_session, Team, Player, PlayerSeasonStats, Transfer
from data.fbref_scraper import FBrefScraper
from utils import logger

def run_pipeline():
    """Ejecuta el ciclo completo de actualización."""
    logger.info("Iniciando Pipeline ETL Automatico...")
    season = config.CURRENT_SEASON
    
    # 1. Inicializar Scraper para ligas nacionales (FBref a veces restringe UCL directa)
    # Usamos Premier League como base para probar el pipeline
    scraper = FBrefScraper(league="ENG-Premier League", season=season)
    
    # 2. Actualizar Estadísticas de Equipos
    logger.info("Step 2: Actualizando xG y metricas de equipos...")
    scraper.update_teams_json_with_xg()
    
    # 3. Actualizar Plantillas y Estadísticas de Jugadores
    logger.info("Step 3: Actualizando plantillas y stats de jugadores...")
    scraper.update_players_json_by_season()
    
    # 4. Sincronizar con Base de Datos SQL
    logger.info("Step 4: Sincronizando con PostgreSQL/SQLite...")
    from data.migrate_json_to_db import migrate
    migrate()
    
    logger.info(f"Pipeline completado para la temporada {season}.")

if __name__ == "__main__":
    run_pipeline()
