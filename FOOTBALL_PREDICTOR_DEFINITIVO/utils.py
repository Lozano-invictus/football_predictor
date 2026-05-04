"""
utils.py
Utilidades compartidas para validación, caché y logging escalable.
"""
import os
import json
import hashlib
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Callable
import functools

import config

# ================================================================ #
# CONFIGURACIÓN DE LOGGING
# ================================================================ #

def setup_logging():
    """Configura logging global."""
    log_file = Path(config.LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Limpiar handlers existentes para evitar conflictos en Windows
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

logger = logging.getLogger(__name__)
setup_logging()


# ================================================================ #
# VALIDACIÓN DE DATOS
# ================================================================ #

class DataValidator:
    """Valida integridad y calidad de datos."""

    @staticmethod
    def validate_team(team: Dict) -> bool:
        """Valida estructura de equipo."""
        required_fields = {"name", "country", "league", "attack", "defense"}
        if not required_fields.issubset(team.keys()):
            logger.warning(f"Equipo incompleto: {team.get('name', 'UNKNOWN')}")
            return False
        
        # Validar rangos
        if not (0 <= team["attack"] <= 5):
            logger.warning(f"Attack inválido para {team['name']}: {team['attack']}")
            return False
        
        if not (0 <= team["defense"] <= 3):
            logger.warning(f"Defense inválido para {team['name']}: {team['defense']}")
            return False
        
        return True

    @staticmethod
    def validate_player(player: Dict, position: str = "striker") -> bool:
        """Valida estructura de jugador."""
        required_fields = {"name", "team", "position", "matches_played", "goals"}
        
        if position == "striker" and "shots_attempted" not in player:
            return False
        
        if position == "goalkeeper" and "saves" not in player:
            return False
        
        if position == "defender" and "tackles" not in player:
            return False
        
        return required_fields.issubset(player.keys())

    @staticmethod
    def format_currency(value: float) -> str:
        """Formatea valor en M€."""
        if value >= 1:
            return f"{value:.1f} M€"
        return f"{value*1000:.0f} K€"

    @staticmethod
    def get_rating_color(rating: float) -> str:
        """Color basado en el rating del jugador."""
        if rating >= 8.0: return "#1d781d" # Verde oscuro
        if rating >= 7.0: return "#2ecc71" # Verde
        if rating >= 6.0: return "#f1c40f" # Amarillo
        return "#e74c3c" # Rojo

    @staticmethod
    def normalize_team_name(name: str) -> str:
        """Normaliza nombres de equipos para evitar duplicados."""
        replacements = {
            "R. Madrid": "Real Madrid",
            "R.Madrid": "Real Madrid",
            "Ath. Madrid": "Atlético Madrid",
            "B. Leverkusen": "Bayer Leverkusen",
            "B.Leverkusen": "Bayer Leverkusen",
            "Borussia Dortmund": "Borussia Dortmund",
            "B. Dortmund": "Borussia Dortmund",
            "Man. City": "Manchester City",
            "Man City": "Manchester City",
            "Man. United": "Manchester United",
            "RB Leipzig": "RB Leipzig",
        }
        
        for old, new in replacements.items():
            if old.lower() in name.lower():
                return new
        
        return name.strip()


# ================================================================ #
# CACHÉ CON TTL
# ================================================================ #

class CacheManager:
    """Maneja caché de datos con time-to-live."""

    def __init__(self, cache_dir: str = config.CACHE_DIR, ttl_hours: int = 6):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)

    def _get_cache_path(self, key: str) -> Path:
        """Genera ruta de archivo caché basada en hash."""
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hash_key}.json"

    def get(self, key: str) -> Optional[Any]:
        """Obtiene valor del caché si está vigente."""
        cache_file = self._get_cache_path(key)
        
        if not cache_file.exists():
            return None

        # Verificar TTL
        modified_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - modified_time > self.ttl:
            cache_file.unlink()
            logger.info(f"Caché expirado: {key}")
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.debug(f"Caché hit: {key}")
            return data
        except Exception as e:
            logger.error(f"Error leyendo caché {key}: {e}")
            return None

    def set(self, key: str, value: Any) -> bool:
        """Almacena valor en caché."""
        cache_file = self._get_cache_path(key)
        
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
            logger.debug(f"Caché set: {key}")
            return True
        except Exception as e:
            logger.error(f"Error escribiendo caché {key}: {e}")
            return False


# ================================================================ #
# DECORADORES PARA CACHÉ
# ================================================================ #

_cache_manager = CacheManager()

def cached(ttl_hours: int = 6):
    """Decorador para cachear resultados de funciones."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            cache_key = f"{func.__name__}_{str(args)}_{str(kwargs)}"
            cached_result = _cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            result = func(*args, **kwargs)
            _cache_manager.set(cache_key, result)
            return result
        return wrapper
    return decorator


# ================================================================ #
# FUNCIONES DE UTILIDAD
# ================================================================ #

def validate_environment() -> bool:
    """Valida que el entorno esté correctamente configurado."""
    checks = {
        "data_dir_exists": os.path.exists(config.DATA_DIR),
        "teams_file_exists": os.path.exists(config.TEAMS_FILE),
        "players_file_exists": os.path.exists(config.PLAYERS_FILE),
    }

    all_ok = all(checks.values())
    
    if all_ok:
        logger.info("✅ Entorno validado correctamente")
    else:
        for check, result in checks.items():
            status = "✅" if result else "❌"
            logger.warning(f"{status} {check}")
    
    return all_ok
