"""
data/api_fetcher.py
Conecta con football-data.org (gratuito) y API-Football (freemium)
para actualizar automáticamente teams.json y players.json con datos reales.

Registro gratuito en: https://www.football-data.org/client/register
"""

import json
import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# CONSTANTES
# ------------------------------------------------------------------ #

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

# Códigos de competición en football-data.org
COMPETITION_CODES = {
    "Champions League": "CL",
    "Premier League":   "PL",
    "La Liga":          "PD",
    "Serie A":          "SA",
    "Bundesliga":       "BL1",
    "Ligue 1":          "FL1",
    "Eredivisie":       "DED",
    "Primeira Liga":    "PPL",
}

LEAGUE_AVG_GOALS = 1.3   # media global para normalizar


# ------------------------------------------------------------------ #
# CLIENTE BASE
# ------------------------------------------------------------------ #

class FootballDataClient:
    """
    Cliente para football-data.org (tier gratuito).
    Límite: 10 llamadas/minuto en el plan gratuito.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Se necesita una API key de football-data.org")
        self.session = requests.Session()
        self.session.headers.update({
            "X-Auth-Token": api_key,
            "Accept":       "application/json",
        })
        self._last_call = 0.0
        self._min_interval = 6.1   # segundos entre llamadas (10/min)

    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """GET con rate-limiting automático."""
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

        url = f"{FOOTBALL_DATA_BASE}/{endpoint.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=15)
        self._last_call = time.time()

        if resp.status_code == 429:
            logger.warning("Rate limit alcanzado — esperando 60s")
            time.sleep(60)
            return self._get(endpoint, params)

        resp.raise_for_status()
        return resp.json()

    # ---------------------------------------------------------------- #
    # EQUIPOS DE UNA COMPETICIÓN
    # ---------------------------------------------------------------- #

    def get_teams(self, competition_code: str,
                  season: Optional[int] = None) -> List[Dict]:
        """
        Devuelve lista de equipos de una competición.
        season: año de inicio de temporada (ej. 2024 para 2024-25).
        """
        params = {}
        if season:
            params["season"] = season
        data = self._get(f"competitions/{competition_code}/teams", params)
        return data.get("teams", [])

    # ---------------------------------------------------------------- #
    # RESULTADOS DE PARTIDOS
    # ---------------------------------------------------------------- #

    def get_matches(self, competition_code: str,
                    season: Optional[int] = None,
                    status: str = "FINISHED") -> List[Dict]:
        """
        Devuelve partidos jugados de una competición.
        status: FINISHED | SCHEDULED | LIVE
        """
        params = {"status": status}
        if season:
            params["season"] = season
        data = self._get(f"competitions/{competition_code}/matches", params)
        return data.get("matches", [])

    # ---------------------------------------------------------------- #
    # STANDINGS
    # ---------------------------------------------------------------- #

    def get_standings(self, competition_code: str,
                      season: Optional[int] = None) -> List[Dict]:
        params = {}
        if season:
            params["season"] = season
        data = self._get(f"competitions/{competition_code}/standings", params)
        standings = data.get("standings", [])
        if standings:
            return standings[0].get("table", [])
        return []

    # ---------------------------------------------------------------- #
    # SCORERS (goleadores)
    # ---------------------------------------------------------------- #

    def get_scorers(self, competition_code: str,
                    season: Optional[int] = None,
                    limit: int = 20) -> List[Dict]:
        params = {"limit": limit}
        if season:
            params["season"] = season
        data = self._get(f"competitions/{competition_code}/scorers", params)
        return data.get("scorers", [])


# ------------------------------------------------------------------ #
# TRANSFORMADORES: API → formato interno JSON
# ------------------------------------------------------------------ #

class DataTransformer:
    """Convierte respuestas de la API al schema de teams.json / players.json."""

    @staticmethod
    def compute_team_strength(matches: List[Dict],
                              team_name: str) -> Tuple[float, float]:
        """
        Calcula attack y defense de un equipo a partir de sus partidos.
        Devuelve (avg_goals_scored, avg_goals_conceded).
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
            round(sum(scored)   / len(scored),   3),
            round(sum(conceded) / len(conceded), 3),
        )

    @staticmethod
    def team_to_internal(api_team: Dict, attack: float,
                         defense: float, league: str) -> Dict:
        """Convierte un equipo de la API al formato de teams.json."""
        area = api_team.get("area", {})
        return {
            "name":       api_team.get("shortName") or api_team.get("name", ""),
            "name_full":  api_team.get("name", ""),
            "country":    area.get("code", "???")[:3],
            "league":     league,
            "attack":     attack,
            "defense":    defense,
            "ucl_titles": 0,    # no disponible en API gratuita
            "rank":       999,
            "last_updated": datetime.utcnow().strftime("%Y-%m-%d"),
        }

    @staticmethod
    def scorer_to_internal(scorer: Dict) -> Dict:
        """Convierte un goleador de la API al formato de players.json."""
        player = scorer.get("player", {})
        team   = scorer.get("team", {})
        goals  = scorer.get("goals", 0) or 0
        # Estimamos disparos como goals * 3.5 (ratio típico UCL)
        shots_est = max(int(goals * 3.5), goals)
        shots_ot  = max(int(goals * 2.0), goals)
        return {
            "name":             player.get("name", "Desconocido"),
            "team":             team.get("shortName", team.get("name", "")),
            "position":         player.get("position", "striker").lower(),
            "matches_played":   scorer.get("playedMatches", 1),
            "goals":            goals,
            "shots_attempted":  shots_est,
            "shots_on_target":  shots_ot,
            "assists":          scorer.get("assists", 0) or 0,
            "last_updated":     datetime.utcnow().strftime("%Y-%m-%d"),
        }


# ------------------------------------------------------------------ #
# ACTUALIZADOR PRINCIPAL
# ------------------------------------------------------------------ #

class DataUpdater:
    """
    Orquesta la actualización completa de teams.json y players.json
    usando datos reales de la temporada actual.
    """

    def __init__(self, api_key: str,
                 teams_path: str = "data/teams.json",
                 players_path: str = "data/players.json"):
        self.client      = FootballDataClient(api_key)
        self.transformer = DataTransformer()
        self.teams_path  = teams_path
        self.players_path = players_path

    # ---------------------------------------------------------------- #
    # ACTUALIZAR EQUIPOS
    # ---------------------------------------------------------------- #

    def update_teams(self,
                     competitions: Dict[str, str] = None,
                     season: int = 2024) -> Dict:
        """
        Actualiza teams.json con datos reales.

        competitions: {nombre_liga: código_api}
                      Si None, usa COMPETITION_CODES completo.
        season: año de inicio de temporada (2024 → 2024-25).

        Devuelve resumen de equipos actualizados.
        """
        if competitions is None:
            competitions = COMPETITION_CODES

        updated = []
        errors  = []

        for league_name, code in competitions.items():
            try:
                logger.info(f"Obteniendo equipos de {league_name} ({code})…")
                teams   = self.client.get_teams(code, season)
                matches = self.client.get_matches(code, season)

                for api_team in teams:
                    name = api_team.get("name", "")
                    att, defn = self.transformer.compute_team_strength(
                        matches, name
                    )
                    internal = self.transformer.team_to_internal(
                        api_team, att, defn, league_name
                    )
                    updated.append(internal)
                    logger.info(f"  ✓ {internal['name']} att={att} def={defn}")

            except requests.HTTPError as e:
                logger.error(f"Error en {league_name}: {e}")
                errors.append({"league": league_name, "error": str(e)})

        if updated:
            self._save_teams(updated)

        return {
            "updated": len(updated),
            "errors":  errors,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ---------------------------------------------------------------- #
    # ACTUALIZAR GOLEADORES
    # ---------------------------------------------------------------- #

    def update_scorers(self,
                       competition_code: str = "CL",
                       season: int = 2024,
                       limit: int = 20) -> Dict:
        """
        Actualiza la sección 'players' (delanteros/goleadores) en players.json.
        """
        try:
            raw = self.client.get_scorers(competition_code, season, limit)
            players = [self.transformer.scorer_to_internal(s) for s in raw]
            self._save_scorers(players)
            logger.info(f"✓ {len(players)} goleadores actualizados")
            return {"updated": len(players),
                    "timestamp": datetime.utcnow().isoformat()}
        except Exception as e:
            logger.error(f"Error actualizando goleadores: {e}")
            return {"updated": 0, "error": str(e)}

    # ---------------------------------------------------------------- #
    # ACTUALIZACIÓN COMPLETA
    # ---------------------------------------------------------------- #

    def full_update(self,
                    competitions: Dict[str, str] = None,
                    season: int = 2024) -> Dict:
        """Actualiza equipos + goleadores en una sola llamada."""
        logger.info("=== Inicio actualización completa ===")
        teams_result   = self.update_teams(competitions, season)
        scorers_result = self.update_scorers("CL", season)
        logger.info("=== Actualización completada ===")
        return {
            "teams":   teams_result,
            "scorers": scorers_result,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ---------------------------------------------------------------- #
    # PERSISTENCIA
    # ---------------------------------------------------------------- #

    def _save_teams(self, teams: List[Dict]) -> None:
        """Guarda equipos actualizados en teams.json."""
        data = {"teams": teams}
        with open(self.teams_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✓ Guardados {len(teams)} equipos en {self.teams_path}")

    def _save_scorers(self, players: List[Dict]) -> None:
        """Guarda goleadores en players.json."""
        try:
            with open(self.players_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"players": [], "goalkeepers": [], "defenders": []}

        data["players"] = players
        with open(self.players_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✓ Guardados {len(players)} goleadores en {self.players_path}")

        with open(self.teams_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"teams.json guardado con {len(data['teams'])} equipos")

    def _save_scorers(self, players: List[Dict]) -> None:
        try:
            with open(self.players_path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"metadata": {}, "players": [], "goalkeepers": [], "defenders": []}

        existing = {p["name"]: p for p in data.get("players", [])}
        for p in players:
            existing[p["name"]] = p
        data["players"] = list(existing.values())
        data["metadata"]["last_updated"] = datetime.utcnow().strftime("%Y-%m-%d")

        with open(self.players_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"players.json guardado con {len(data['players'])} jugadores")


# ------------------------------------------------------------------ #
# CLI rápida  (python data/api_fetcher.py)
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import sys

    key = os.getenv("FOOTBALL_DATA_KEY") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not key:
        print("Uso: python data/api_fetcher.py <API_KEY>")
        print("  o: FOOTBALL_DATA_KEY=<key> python data/api_fetcher.py")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    updater = DataUpdater(key)
    # Actualiza solo UCL por defecto para no gastar requests
    result = updater.update_teams({"Champions League": "CL"}, season=2024)
    result2 = updater.update_scorers("CL", season=2024)
    print(json.dumps({"teams": result, "scorers": result2}, indent=2))
