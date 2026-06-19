
"""
data/api_fetcher.py
Conecta con football-data.org (gratuito) para actualizar automáticamente
la base de datos SQLite con datos reales de equipos, plantillas, partidos y goleadores.

MEJORAS IMPLEMENTADAS:
- Logging detallado a archivo logs/api.log
- Reintentos automáticos con backoff exponencial
- Manejo robusto de errores HTTP
- Fallback inteligente si un endpoint no está disponible
- Timeout de 30 segundos
- Diagnóstico completo de cada request

Registro gratuito: https://www.football-data.org/client/register
"""

import json
import os
import time
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import requests

from data.database import get_session, Team, Player, PlayerSeasonStats, Match
from data.loader import DataLoader


# ------------------------------ #
# LOGGING BOOTSTRAP (centralizado en utils.py)
# ------------------------------ #
logger = logging.getLogger(__name__)


# ------------------------------ #
# CONSTANTES Y CONFIGURACIÓN API
# ------------------------------ #
FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

COMPETITION_CODES = {
    "Champions League": "CL",
    "Premier League": "PL",
    "La Liga": "PD",
    "Serie A": "SA",
    "Bundesliga": "BL1",
    "Ligue 1": "FL1",
    "Eredivisie": "DED",
    "Primeira Liga": "PPL",
}

LEAGUE_AVG_GOALS = 1.3
REQUEST_TIMEOUT = 30
MAX_RETRIES = 5
BACKOFF_FACTOR = 2  # 1s, 2s, 4s, 8s, 16s


# ------------------------------ #
# CLIENTE API CON REINTENTOS
# ------------------------------ #
class ApiAuthError(RuntimeError):
    pass

class ApiForbiddenError(RuntimeError):
    pass

class ApiRateLimitError(RuntimeError):
    pass

class ApiServerError(RuntimeError):
    pass

class ApiNetworkError(RuntimeError):
    pass


class FootballDataClient:
    """
    Cliente para football-data.org con reintentos, backoff y mapeo explícito de errores.
    Límite: 10 requests/minuto en el plan gratuito.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Se requiere una clave de API de football-data.org")
        self.session = requests.Session()
        self.session.headers.update({
            "X-Auth-Token": api_key,
            "Accept": "application/json",
        })
        self._last_call = 0.0
        self._min_interval = 6.1  # segundos entre llamadas (10/min)
        logger.info("FootballDataClient inicializado correctamente")

    def _wait_rate_limit(self):
        """Espera para respetar el límite de tasa."""
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            wait_time = self._min_interval - elapsed
            logger.debug(f"Respetando límite de tasa: esperando {wait_time:.2f}s")
            time.sleep(wait_time)

    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """
        GET con reintentos y backoff exponencial.
        Mapea errores a excepciones de dominio para que DataUpdater pueda
        definir estado OK/PARTIAL/FAIL y reportar correctamente.
        """
        url = f"{FOOTBALL_DATA_BASE}/{endpoint.lstrip('/')}"
        attempt = 0
        last_exception: Optional[Exception] = None

        while attempt < MAX_RETRIES:
            attempt += 1
            try:
                self._wait_rate_limit()
                logger.debug(f"Request #{attempt} a: {url} con params: {params}")

                response = self.session.get(
                    url,
                    params=params,
                    timeout=REQUEST_TIMEOUT
                )

                self._last_call = time.time()

                if response.status_code == 200:
                    result = response.json()
                    logger.debug(f"Respuesta exitosa de {url}")
                    return result

                remaining = response.headers.get("x-ratelimit-remaining")
                retry_after = response.headers.get("Retry-After")
                if remaining is not None or retry_after is not None:
                    logger.debug(
                        f"Rate-limit headers for {url}: remaining={remaining}, Retry-After={retry_after}"
                    )

                body_preview = (response.text or "")[:200]
                logger.warning(f"Error HTTP {response.status_code} en {url}: {body_preview}")

                if response.status_code == 401:
                    raise ApiAuthError(body_preview)
                if response.status_code == 403:
                    raise ApiForbiddenError(body_preview)

                if response.status_code == 429:
                    retry_after_seconds: Optional[int] = None
                    if retry_after:
                        try:
                            retry_after_seconds = int(float(retry_after))
                        except Exception:
                            retry_after_seconds = None

                    wait_seconds = max(1, retry_after_seconds) if retry_after_seconds is not None else (BACKOFF_FACTOR ** (attempt - 1))
                    logger.warning(
                        f"429 Rate Limit para {url}. Esperando {wait_seconds}s antes de reintentar "
                        f"(intentos restantes: {MAX_RETRIES - attempt})"
                    )
                    time.sleep(wait_seconds)
                    last_exception = ApiRateLimitError(body_preview)
                    continue

                if response.status_code == 400:
                    # No reintentar 400: devuelve estructura vacía
                    # (el pipeline la tratará como PARTIAL/OK según corresponda).
                    return {}

                if response.status_code >= 500:
                    wait_seconds = BACKOFF_FACTOR ** (attempt - 1)
                    logger.warning(
                        f"Reintentando {url} en {wait_seconds}s (server error). "
                        f"(intentos restantes: {MAX_RETRIES - attempt})"
                    )
                    time.sleep(wait_seconds)
                    last_exception = ApiServerError(body_preview)
                    continue

                raise requests.HTTPError(body_preview, response=response)

            except requests.Timeout as e:
                logger.warning(f"Timeout en {url} (intento #{attempt})")
                wait_seconds = BACKOFF_FACTOR ** (attempt - 1)
                time.sleep(wait_seconds)
                last_exception = ApiNetworkError(str(e))
                continue

            except requests.ConnectionError as e:
                logger.warning(f"Error de conexión en {url} (intento #{attempt})")
                wait_seconds = BACKOFF_FACTOR ** (attempt - 1)
                time.sleep(wait_seconds)
                last_exception = ApiNetworkError(str(e))
                continue

            except Exception as e:
                logger.error(f"Error inesperado en {url} (intento #{attempt}): {e}")
                wait_seconds = BACKOFF_FACTOR ** (attempt - 1)
                time.sleep(wait_seconds)
                last_exception = e if isinstance(e, Exception) else Exception(str(e))
                continue

        logger.error(f"Todos los {MAX_RETRIES} intentos fallaron para {url}")
        if last_exception:
            raise last_exception from None
        raise Exception(f"Todos los {MAX_RETRIES} intentos fallaron para {url}")

    # ------------------------------ #
    # MÉTODOS ESPECÍFICOS DE LA API
    # ------------------------------ #

    def get_teams(self, competition_code: str,
                  season: Optional[int] = None) -> List[Dict]:
        """Obtiene equipos de una competición. Tiene fallback si la temporada no está disponible."""
        params = {}
        if season:
            params["season"] = season

        try:
            data = self._get(f"competitions/{competition_code}/teams", params)
            return data.get("teams", [])
        except requests.HTTPError as e:
            if season and (e.response is not None and e.response.status_code == 400):
                logger.warning(
                    f"No hay datos de equipos para temporada {season}, intentando sin temporada"
                )
                data = self._get(f"competitions/{competition_code}/teams", {})
                return data.get("teams", [])
            raise

    def get_matches(self, competition_code: str,
                    season: Optional[int] = None,
                    status: str = "FINISHED") -> List[Dict]:
        """Obtiene partidos de una competición. Tiene fallback si la temporada no está disponible."""
        params = {"status": status}
        if season:
            params["season"] = season

        try:
            data = self._get(f"competitions/{competition_code}/matches", params)
            return data.get("matches", [])
        except requests.HTTPError as e:
            if season and (e.response is not None and e.response.status_code == 400):
                logger.warning(
                    f"No hay datos de partidos para temporada {season}, intentando sin temporada"
                )
                data = self._get(f"competitions/{competition_code}/matches", {"status": status})
                return data.get("matches", [])
            raise

    def get_scorers(self, competition_code: str,
                    season: Optional[int] = None,
                    limit: int = 20) -> List[Dict]:
        """
        Obtiene goleadores de una competición.
        Si el endpoint falla, devuelve lista vacía para no bloquear el resto de la actualización.
        """
        params = {"limit": limit}
        if season:
            params["season"] = season

        try:
            data = self._get(f"competitions/{competition_code}/scorers", params)
            return data.get("scorers", [])
        except Exception as e:
            logger.warning(
                f"Endpoint goleadores no disponible o falló. Error: {e}"
            )
            logger.warning(
                "ⓘ La actualización continuará sin datos de goleadores"
            )
            return []

    def get_standings(self, competition_code: str,
                      season: Optional[int] = None) -> List[Dict]:
        """Obtiene clasificación de una competición."""
        params = {}
        if season:
            params["season"] = season
        try:
            data = self._get(f"competitions/{competition_code}/standings", params)
            standings = data.get("standings", [])
            if standings:
                return standings[0].get("table", [])
            return []
        except Exception as e:
            logger.warning(
                f"Endpoint standings no disponible o falló. Error: {e}"
            )
            return []


# ------------------------------ #
# TRANSFORMADORES: API -> BD
# ------------------------------ #
class DataTransformer:
    """Convierte respuestas de la API al modelo de la base de datos."""

    @staticmethod
    def _parse_date(value: Optional[str]):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def compute_team_strength(matches: List[Dict],
                              team_name: str) -> Tuple[float, float]:
        """
        Calcula ataque y defensa de un equipo basándose en sus partidos.
        Devuelve (goles_a_favor_promedio, goles_en_contra_promedio).
        """
        scored = []
        conceded = []
        for m in matches:
            if m.get("status") != "FINISHED":
                continue
            home = m["homeTeam"]["name"]
            away = m["awayTeam"]["name"]
            hg = m["score"]["fullTime"].get("home", 0) or 0
            ag = m["score"]["fullTime"].get("away", 0) or 0

            if home == team_name:
                scored.append(hg)
                conceded.append(ag)
            elif away == team_name:
                scored.append(ag)
                conceded.append(hg)

        if not scored:
            return LEAGUE_AVG_GOALS, LEAGUE_AVG_GOALS

        return (
            round(sum(scored) / len(scored), 3),
            round(sum(conceded) / len(conceded), 3),
        )

    @staticmethod
    def api_team_to_db_team(api_team: Dict, attack: float,
                          defense: float, league: str) -> Team:
        area = api_team.get("area", {})
        return Team(
            name=api_team.get("shortName") or api_team.get("name", ""),
            country=area.get("code", "???")[:3],
            league=league,
            attack=attack,
            defense=defense,
            elo=1500.0,
            rank=999,
            short_name=api_team.get("shortName", ""),
            logo_url=api_team.get("crest", ""),
            stadium=api_team.get("venue", ""),
            ucl_titles=0,
            last_updated=datetime.utcnow().isoformat()
        )

    @staticmethod
    def api_player_to_db_player(api_player: Dict, team_id: int = None) -> Player:
        return Player(
            name=api_player.get("name", "Desconocido"),
            full_name=api_player.get("name", "Desconocido"),
            nationality=api_player.get("nationality", ""),
            position=api_player.get("position", "striker").lower(),
            position_main=api_player.get("position", "striker").lower(),
            date_of_birth=DataTransformer._parse_date(api_player.get("dateOfBirth")),
            is_active=True,
        )


# ------------------------------ #
# ACTUALIZADOR PRINCIPAL DE BD
# ------------------------------ #
class DataUpdater:
    """Orquesta la actualización completa de la base de datos desde la API."""

    def __init__(self, api_key: str):
        self.client = FootballDataClient(api_key)
        self.transformer = DataTransformer()
        self.loader = DataLoader()

    def update_teams_in_db(self,
                         competitions: Dict[str, str] = None,
                         season: int = 2023) -> Dict:
        """
        Actualiza la tabla de equipos en la BD.
        Devuelve pipeline_status: OK | PARTIAL | FAIL.
        - OK: todas las ligas procesadas sin errores
        - PARTIAL: algunas ligas fallaron, pero se committeó lo demás
        - FAIL: rollback global por error no recuperable
        """
        if competitions is None:
            competitions = COMPETITION_CODES

        updated_count = 0
        errors: List[Dict] = []
        session = get_session()

        pipeline_status = "OK"
        try:
            for league_name, code in competitions.items():
                try:
                    logger.info(f"Obteniendo equipos de {league_name} ({code})...")
                    teams_api = self.client.get_teams(code, season)
                    matches_api = self.client.get_matches(code, season)

                    for api_team in teams_api:
                        team_name = api_team.get("name", "")
                        short_name = api_team.get("shortName", "")

                        existing_team = session.query(Team).filter(
                            (Team.name == team_name) | (Team.short_name == short_name)
                        ).first()

                        att, defns = self.transformer.compute_team_strength(matches_api, team_name)

                        if existing_team:
                            existing_team.attack = att
                            existing_team.defense = defns
                            existing_team.logo_url = api_team.get("crest", existing_team.logo_url)
                            existing_team.stadium = api_team.get("venue", existing_team.stadium)
                            existing_team.last_updated = datetime.utcnow().isoformat()
                            logger.debug(f"  ↻ Actualizado: {existing_team.name}")
                        else:
                            db_team = self.transformer.api_team_to_db_team(api_team, att, defns, league_name)
                            session.add(db_team)
                            session.flush()
                            logger.debug(f"  + Nuevo: {db_team.name}")

                        updated_count += 1

                except Exception as e:
                    pipeline_status = "PARTIAL"
                    logger.error(f"Error al procesar {league_name}: {e}")
                    errors.append({"league": league_name, "error": str(e)})

            session.commit()
            logger.info(f"✅ Commit exitoso: {updated_count} equipos actualizados en BD (status={pipeline_status})")

        except Exception as e:
            session.rollback()
            pipeline_status = "FAIL"
            logger.error(f"Error al actualizar equipos: {e}")
            errors.append({"league": "ALL", "error": str(e)})
        finally:
            session.close()

        return {
            "updated": updated_count,
            "pipeline_status": pipeline_status,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def update_scorers_in_db(self,
                            competition_code: str = "CL",
                            season: Optional[int] = 2023,
                            limit: int = 20) -> Dict:
        """
        Actualiza goleadores en la BD.
        Devuelve estructura con pipeline_status: OK | PARTIAL | FAIL (mínimo parcial cuando el endpoint no devuelve datos).
        """
        season_str = f"{season}-{season + 1}" if season else "current"
        updated_count = 0
        session = get_session()

        pipeline_status = "OK"
        error_detail: Optional[str] = None

        try:
            raw_scorers = self.client.get_scorers(competition_code, season, limit)

            # Si el endpoint no trae datos, tratamos como PARTIAL (no FAIL) para no bloquear el pipeline global
            if not raw_scorers:
                pipeline_status = "PARTIAL"

            for scorer in raw_scorers:
                api_player = scorer.get("player", {})
                api_team = scorer.get("team", {})
                player_name = api_player.get("name", "")
                team_name = api_team.get("shortName", api_team.get("name", ""))

                db_player = session.query(Player).filter(Player.name == player_name).first()

                if not db_player:
                    db_player = Player(
                        name=player_name,
                        full_name=player_name,
                        nationality=api_player.get("nationality", ""),
                        position=api_player.get("position", "striker").lower(),
                        position_main=api_player.get("position", "striker").lower(),
                        date_of_birth=self.transformer._parse_date(api_player.get("dateOfBirth")),
                        is_active=True,
                    )
                    session.add(db_player)
                    session.flush()

                db_team = session.query(Team).filter(
                    (Team.name == team_name) | (Team.short_name == team_name)
                ).first()
                if not db_team:
                    pipeline_status = "PARTIAL"
                    error_detail = f"Equipo no encontrado para goleador: {team_name}"
                    logger.warning(error_detail)
                    continue
                team_id = db_team.id

                ps_stats = session.query(PlayerSeasonStats).filter(
                    PlayerSeasonStats.player_id == db_player.id,
                    PlayerSeasonStats.season == season_str
                ).first()

                goals = scorer.get("goals", 0) or 0
                assists = scorer.get("assists", 0) or 0

                if ps_stats:
                    ps_stats.goals = goals
                    ps_stats.assists = assists
                    ps_stats.matches_played = scorer.get("playedMatches", 1)
                    ps_stats.last_updated = datetime.utcnow().isoformat()
                else:
                    ps_stats = PlayerSeasonStats(
                        player_id=db_player.id,
                        team_id=team_id,
                        season=season_str,
                        goals=goals,
                        assists=assists,
                        matches_played=scorer.get("playedMatches", 1),
                        last_updated=datetime.utcnow().isoformat()
                    )
                    session.add(ps_stats)

                updated_count += 1

            session.commit()
            logger.info(f"✅ Commit exitoso: {updated_count} goleadores actualizados en BD (status={pipeline_status})")

        except Exception as e:
            session.rollback()
            pipeline_status = "FAIL"
            error_detail = str(e)
            logger.error(f"Error al actualizar goleadores: {e}")

        finally:
            session.close()

        return {
            "updated": updated_count,
            "pipeline_status": pipeline_status,
            "error": error_detail,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def full_db_update(self,
                      competitions: Dict[str, str] = None,
                      season: int = 2023) -> Dict:
        """Actualiza equipos y goleadores en la BD de forma robusta."""
        logger.info("=" * 60)
        logger.info("INICIO DE ACTUALIZACIÓN COMPLETA DE BD")
        logger.info("=" * 60)

        teams_result = self.update_teams_in_db(competitions, season)
        scorers_result = self.update_scorers_in_db("CL", season)

        logger.info("=" * 60)
        logger.info("ACTUALIZACIÓN COMPLETA TERMINADA")
        logger.info("=" * 60)

        return {
            "teams": teams_result,
            "scorers": scorers_result,
            "timestamp": datetime.utcnow().isoformat(),
        }


# ------------------------------ #
# EJECUCIÓN POR LÍNEA DE COMANDOS
# ------------------------------ #
if __name__ == "__main__":
    # Cargar API key de variables de entorno o argumento
    API_KEY = (
        os.getenv("FOOTBALL_DATA_API_KEY")
        or os.getenv("FOOTBALL_DATA_KEY")
        or (sys.argv[1] if len(sys.argv) > 1 else "")
    )

    if not API_KEY:
        print("Uso: python data/api_fetcher.py <API_KEY>")
        print("  o: FOOTBALL_DATA_API_KEY=<key> python data/api_fetcher.py")
        sys.exit(1)

    updater = DataUpdater(API_KEY)
    result = updater.full_db_update({"Champions League": "CL"}, season=2023)

    print("\n" + "=" * 60)
    print("RESUMEN DE LA ACTUALIZACIÓN")
    print("=" * 60)
    print(f"Equipos actualizados: {result['teams']['updated']}")
    print(f"Goleadores actualizados: {result['scorers']['updated']}")
    print(f"Errores: {len(result['teams']['errors'])}")
    if result['teams']['errors']:
        for err in result['teams']['errors']:
            print(f"- {err['league']}: {err['error']}")
    print("\nLogs detallados en: logs/api.log")
