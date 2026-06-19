"""
data/loader.py – carga, validación y persistencia de datos usando SQLite.
Permite agregar/editar equipos y jugadores sin tocar el código del modelo.
"""
from typing import Dict, List, Optional
import pandas as pd
import config
from data.database import get_session, Team, Player, PlayerSeasonStats, TeamSeasonStats


TEAM_COLUMNS = [
    "id", "name", "short_name", "country", "league", "logo_url", "stadium",
    "ucl_titles", "attack", "defense", "elo", "rank", "last_updated",
]

PLAYER_COLUMNS = [
    "id", "name", "full_name", "nationality", "date_of_birth", "image_url",
    "position", "is_active",
]


class DataLoader:
    """Gestiona lectura/escritura de datos desde la base de datos SQLite."""

    def __init__(self):
        self.current_season = config.CURRENT_SEASON

    @staticmethod
    def _team_to_dict(team: Team) -> Dict:
        return {
            "id": team.id,
            "name": team.name,
            "short_name": team.short_name,
            "country": team.country,
            "league": team.league,
            "logo_url": team.logo_url,
            "stadium": team.stadium,
            "ucl_titles": team.ucl_titles or 0,
            "attack": team.attack if team.attack is not None else 1.0,
            "defense": team.defense if team.defense is not None else 1.0,
            "elo": team.elo if team.elo is not None else 1500.0,
            "rank": team.rank if team.rank is not None else 999,
            "last_updated": team.last_updated,
        }

    @staticmethod
    def _player_to_dict(player: Player) -> Dict:
        pos = player.position_main or player.position
        return {
            "id": player.id,
            "name": player.name,
            "full_name": player.full_name,
            "nationality": player.nationality,
            "date_of_birth": player.date_of_birth,
            "image_url": player.image_url,
            "position": pos,
            "is_active": player.is_active,
        }

    # ------------------------------------------------------------------ #
    # EQUIPOS
    # ------------------------------------------------------------------ #

    def load_teams(
        self,
        season: Optional[str] = None,
        only_active: bool = True,
        force: bool = False
    ) -> List[Dict]:
        """Load teams, optionally filtered by season and active status"""
        target_season = season or self.current_season
        session = get_session()
        try:
            teams = session.query(Team).all()
            return [self._team_to_dict(t) for t in teams]
        finally:
            session.close()

    def teams_df(
        self,
        season: Optional[str] = None,
        only_active: bool = True
    ) -> pd.DataFrame:
        return pd.DataFrame(self.load_teams(season, only_active), columns=TEAM_COLUMNS)

    def get_team(self, name: str) -> Optional[Dict]:
        if not name:
            return None
        session = get_session()
        try:
            team = session.query(Team).filter(Team.name.ilike(name)).first()
            return self._team_to_dict(team) if team else None
        finally:
            session.close()

    def add_or_update_team(self, team: Dict) -> None:
        """Añade un equipo nuevo o actualiza uno existente por nombre."""
        required = {"name", "country", "league", "attack", "defense"}
        if not required.issubset(team.keys()):
            raise ValueError(f"El equipo debe tener los campos: {required}")
        
        session = get_session()
        existing_team = session.query(Team).filter(Team.name.ilike(team["name"])).first()
        
        if existing_team:
            for key, value in team.items():
                if hasattr(existing_team, key):
                    setattr(existing_team, key, value)
        else:
            new_team = Team(
                name=team.get("name"),
                short_name=team.get("short_name"),
                country=team.get("country"),
                league=team.get("league"),
                logo_url=team.get("logo_url"),
                stadium=team.get("stadium"),
                ucl_titles=team.get("ucl_titles", 0),
                attack=team.get("attack", 1.0),
                defense=team.get("defense", 1.0),
                elo=team.get("elo", 1500.0),
                rank=team.get("rank", 999),
                last_updated=team.get("last_updated"),
            )
            session.add(new_team)
        
        session.commit()
        session.close()

    def delete_team(self, name: str) -> bool:
        if not name:
            return False
        session = get_session()
        team = session.query(Team).filter(Team.name.ilike(name)).first()
        if team:
            session.delete(team)
            session.commit()
            session.close()
            return True
        session.close()
        return False

    # ------------------------------------------------------------------ #
    # JUGADORES
    # ------------------------------------------------------------------ #

    def load_players(
        self,
        position: str = "all",
        season: Optional[str] = None,
        only_active: bool = True
    ) -> List[Dict]:
        """
        position: 'strikers', 'goalkeepers', 'defenders', 'all'
        season: filter by season stats (defaults to current season
        """
        target_season = season or self.current_season
        session = get_session()
        
        players_query = session.query(Player)
        
        if only_active:
            players_query = players_query.filter(Player.is_active.is_(True))
        
        try:
            players = players_query.all()
            player_dicts = [self._player_to_dict(p) for p in players]
        finally:
            session.close()
        
        if position == "strikers":
            return [p for p in player_dicts if p.get("position") in ["ST", "CF", "FW", "striker"]]
        if position == "goalkeepers":
            return [p for p in player_dicts if p.get("position") in ["GK", "goalkeeper"]]
        if position == "defenders":
            return [p for p in player_dicts if p.get("position") in ["CB", "RB", "LB", "DF", "defender"]]
            
        return player_dicts

    def strikers_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.load_players("strikers"), columns=PLAYER_COLUMNS)

    def goalkeepers_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.load_players("goalkeepers"), columns=PLAYER_COLUMNS)

    def defenders_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.load_players("defenders"), columns=PLAYER_COLUMNS)

    def add_or_update_player(self, player: Dict, position: Optional[str] = None) -> None:
        """Añade un jugador nuevo o actualiza uno existente por nombre."""
        if not player.get("name"):
            raise ValueError("El jugador debe tener nombre")

        session = get_session()
        existing_player = session.query(Player).filter(Player.name.ilike(player.get("name"))).first()
        
        if existing_player:
            for key, value in player.items():
                if hasattr(existing_player, key):
                    setattr(existing_player, key, value)
            if position:
                existing_player.position = position
                existing_player.position_main = position
        else:
            new_player = Player(
                name=player.get("name"),
                full_name=player.get("full_name"),
                nationality=player.get("nationality"),
                date_of_birth=player.get("date_of_birth"),
                image_url=player.get("image_url"),
                position_main=position or player.get("position"),
                position=position or player.get("position"),
                is_active=player.get("is_active", True),
            )
            session.add(new_player)
            
        session.commit()
        session.close()

    # ------------------------------------------------------------------ #
    # TEMPORADAS
    # ------------------------------------------------------------------ #

    def get_available_seasons(self) -> List[str]:
        """Get list of all seasons present in the database"""
        session = get_session()
        
        team_seasons = session.query(TeamSeasonStats.season).distinct().all()
        player_seasons = session.query(PlayerSeasonStats.season).distinct().all()
        
        all_seasons = set()
        for s in team_seasons:
            if s[0]:
                all_seasons.add(s[0])
        for s in player_seasons:
            if s[0]:
                all_seasons.add(s[0])
        
        session.close()
        return sorted(list(all_seasons))

    def get_current_season_label(self) -> str:
        return self.current_season
