# config.py – parámetros globales del modelo y configuración escalable

import os
from pathlib import Path

# ================================================================ #
# DIRECTORIOS Y RUTAS
# ================================================================ #
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR: str = (PROJECT_ROOT / "data").as_posix()
TEAMS_FILE: str = (PROJECT_ROOT / "data" / "teams.json").as_posix()
PLAYERS_FILE: str = (PROJECT_ROOT / "data" / "players.json").as_posix()
CACHE_DIR: str = (PROJECT_ROOT / "data" / "cache").as_posix()
DB_PATH: str = (PROJECT_ROOT / "data" / "football_predictor.db").as_posix()

# Crear directorios si no existen
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(PROJECT_ROOT / "logs", exist_ok=True)

# ================================================================ #
# PARÁMETROS DEL MODELO 2024-25 (Fuente: Murillo García, 2025)
# ================================================================ #
LEAGUE_AVG_GOALS: float = 1.63   # media goles UCL 2024-25
AVG_DISTANCE_KM: float = 117.41 # distancia media recorrida
HOME_ADVANTAGE: float = 1.10    # multiplicador ventaja local
MAX_GOALS: int = 9              # máximo goles (visto en 2024-25)
MIN_TEAM_ATTACK: float = 0.8    # mínimo ataque permitido
MAX_TEAM_ATTACK: float = 3.5    # máximo ataque permitido

# Dixon-Coles specific
RHO_CORRECTION: bool = True     # aplicar corrección de correlación para marcadores bajos
TIME_DECAY_XI: float = 0.0019   # parámetro de decaimiento temporal (Dixon-Coles)

# ================================================================ #
# REGRESIÓN LINEAL DE JUGADORES
# ================================================================ #
MIN_MATCHES_PLAYED: int = 5     # filtro mínimo de partidos
MODEL_R2_THRESHOLD: float = 0.7 # umbral mínimo de R² para validar modelo
OUTLIER_STD_THRESHOLD: float = 2.0  # desviación estándar para detectar outliers

# ================================================================ #
# SIMULADOR DE TORNEO (MONTE CARLO)
# ================================================================ #
N_SIMULATIONS: int = 10_000     # iteraciones para simulación completa
N_SIMULATIONS_FAST: int = 1_000 # iteraciones para demostración rápida
RANDOM_SEED: int = 42           # seed para reproducibilidad

# ================================================================ #
# CONFIGURACIÓN DE APIS Y SCRAPING
# ================================================================ #
SCRAPING_ENABLED: bool = True
SCRAPING_INTERVAL_HOURS: int = 6  # caché de 6 horas para datos externos
API_FOOTBALL_DATA_ORG_KEY: str = os.getenv("FOOTBALL_DATA_API_KEY", "")

# Códigos de competición en football-data.org
COMPETITIONS = {
    "Champions League": "CL",
    "Premier League":   "PL",
    "La Liga":          "PD",
    "Serie A":          "SA",
    "Bundesliga":       "BL1",
    "Ligue 1":          "FL1",
}

# ================================================================ #
# GESTIÓN DE TEMPORADAS DINÁMICAS
# ================================================================ #
from datetime import datetime

def get_current_season():
    year = datetime.now().year
    # Champions cruza años
    if datetime.now().month >= 7:
        return f"{year}-{year+1}"
    else:
        return f"{year-1}-{year}"

CURRENT_SEASON = get_current_season() # Ej: 2025-2026

# ================================================================ #
# PARÁMETROS DEL MODELO HÍBRIDO
# ================================================================ #
HYBRID_CURRENT_WEIGHT: float = 0.4    # Peso del xG actual
HYBRID_HISTORICAL_WEIGHT: float = 0.6 # Peso del xG histórico
TRANSFER_IMPACT_COEFF: float = 0.15   # Impacto de fichajes en la fuerza
FORM_WEIGHT: float = 0.25             # Peso de la racha reciente
BASE_XG_WEIGHT: float = 0.6           # Peso del xG base
OFFICIAL_SOURCES = {
    "UEFA_UCL_STATS": "https://www.uefa.com/uefachampionsleague/statistics/",
    "FBREF_UCL": "https://fbref.com/en/comps/8/Champions-League-Stats",
    "FOOTBALL_DATA_API": "https://www.football-data.org/"
}

# ================================================================ #
# PARÁMETROS DE ELO RATING
# ================================================================ #
ELO_K_FACTOR: int = 32          # Sensibilidad del cambio de Elo
ELO_INITIAL_RATING: int = 1500  # Rating base para nuevos equipos
LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FILE: str = (PROJECT_ROOT / "logs" / "football_predictor.log").as_posix()  # Archivo de logs

# ================================================================ #
# FEATURE FLAGS
# ================================================================ #
FEATURES = {
    "ADVANCED_STATS": True,
    "DIXON_COLES": True,
    "SQL_DATABASE": True,
    "LIVE_UPDATES": True,
    "EXPORT_PDF": True,
}
