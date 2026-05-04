"""
data/loader.py – carga, validación y persistencia de datos.
Permite agregar/editar equipos y jugadores sin tocar el código del modelo.
"""
import json
import os
from typing import Dict, List, Optional

import pandas as pd


class DataLoader:
    """Gestiona lectura/escritura de teams.json y players.json."""

    def __init__(self, teams_path: str = "data/teams.json",
                 players_path: str = "data/players.json"):
        self.teams_path = teams_path
        self.players_path = players_path
        self._teams_cache: Optional[Dict] = None
        self._players_cache: Optional[Dict] = None

    # ------------------------------------------------------------------ #
    # EQUIPOS
    # ------------------------------------------------------------------ #

    def load_teams(self, force: bool = False) -> List[Dict]:
        if self._teams_cache is None or force:
            with open(self.teams_path, encoding="utf-8") as f:
                self._teams_cache = json.load(f)
        return self._teams_cache["teams"]

    def teams_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.load_teams())

    def get_team(self, name: str) -> Optional[Dict]:
        for t in self.load_teams():
            if t["name"].lower() == name.lower():
                return t
        return None

    def add_or_update_team(self, team: Dict) -> None:
        """Añade un equipo nuevo o actualiza uno existente por nombre."""
        required = {"name", "country", "league", "attack", "defense"}
        if not required.issubset(team.keys()):
            raise ValueError(f"El equipo debe tener los campos: {required}")
        data = self._load_raw_teams()
        idx = next((i for i, t in enumerate(data["teams"])
                    if t["name"].lower() == team["name"].lower()), None)
        if idx is not None:
            data["teams"][idx].update(team)
        else:
            team.setdefault("ucl_titles", 0)
            team.setdefault("rank", 999)
            data["teams"].append(team)
        self._save_teams(data)
        self._teams_cache = None          # invalidar caché

    def delete_team(self, name: str) -> bool:
        data = self._load_raw_teams()
        before = len(data["teams"])
        data["teams"] = [t for t in data["teams"]
                         if t["name"].lower() != name.lower()]
        if len(data["teams"]) < before:
            self._save_teams(data)
            self._teams_cache = None
            return True
        return False

    # ------------------------------------------------------------------ #
    # JUGADORES
    # ------------------------------------------------------------------ #

    def load_players(self, position: str = "all") -> List[Dict]:
        """position: 'strikers', 'goalkeepers', 'defenders', 'all'"""
        if self._players_cache is None:
            with open(self.players_path, encoding="utf-8") as f:
                self._players_cache = json.load(f)
        data = self._players_cache
        if position == "strikers":
            return data["players"]
        if position == "goalkeepers":
            return data["goalkeepers"]
        if position == "defenders":
            return data["defenders"]
        return data["players"] + data["goalkeepers"] + data["defenders"]

    def strikers_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.load_players("strikers"))

    def goalkeepers_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.load_players("goalkeepers"))

    def defenders_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.load_players("defenders"))

    def add_or_update_player(self, player: Dict, position: str) -> None:
        """position: 'players' | 'goalkeepers' | 'defenders'"""
        if position not in ("players", "goalkeepers", "defenders"):
            raise ValueError("position debe ser 'players', 'goalkeepers' o 'defenders'")
        with open(self.players_path, encoding="utf-8") as f:
            data = json.load(f)
        idx = next((i for i, p in enumerate(data[position])
                    if p["name"].lower() == player["name"].lower()), None)
        if idx is not None:
            data[position][idx].update(player)
        else:
            data[position].append(player)
        with open(self.players_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._players_cache = None

    # ------------------------------------------------------------------ #
    # PRIVADOS
    # ------------------------------------------------------------------ #

    def _load_raw_teams(self) -> Dict:
        with open(self.teams_path, encoding="utf-8") as f:
            return json.load(f)

    def _save_teams(self, data: Dict) -> None:
        with open(self.teams_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
