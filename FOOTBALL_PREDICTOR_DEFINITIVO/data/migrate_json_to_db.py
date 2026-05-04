"""
data/migrate_json_to_db.py
Script para migrar datos de los archivos JSON a la base de datos SQLite.
Soporta el nuevo modelo temporal multi-temporada.
"""

import json
import os
import sys
from pathlib import Path

# Añadir el directorio raíz al path para importar módulos locales
sys.path.append(str(Path(__file__).parent.parent))

from data.database import init_db, get_session, Team, Player, PlayerSeasonStats
import config

def migrate():
    print("🚀 Iniciando migración multi-temporada (JSON -> SQLite)...")
    init_db()
    session = get_session()
    
    current_season = config.CURRENT_SEASON

    # 1. Migrar Equipos
    if os.path.exists(config.TEAMS_FILE):
        with open(config.TEAMS_FILE, 'r', encoding='utf-8') as f:
            teams_data = json.load(f)
            for t in teams_data.get("teams", []):
                existing = session.query(Team).filter_by(name=t["name"]).first()
                if not existing:
                    new_team = Team(
                        name=t["name"],
                        country=t["country"],
                        league=t["league"],
                        attack=t["attack"],
                        defense=t["defense"],
                        ucl_titles=t.get("ucl_titles", 0),
                        rank=t.get("rank", 999)
                    )
                    session.add(new_team)
        session.commit()
        print(f"✅ Equipos migrados.")

    # 2. Migrar Jugadores y Estadísticas Temporales
    if os.path.exists(config.PLAYERS_FILE):
        with open(config.PLAYERS_FILE, 'r', encoding='utf-8') as f:
            players_data = json.load(f)
            for pos in ["players", "goalkeepers", "defenders"]:
                for p in players_data.get(pos, []):
                    # a. Asegurar que el jugador existe en la tabla maestra
                    player = session.query(Player).filter_by(name=p["name"]).first()
                    if not player:
                        player = Player(name=p["name"], position=p.get("position", pos))
                        session.add(player)
                        session.flush() # Para obtener el ID

                    # b. Asegurar que el equipo existe
                    team = session.query(Team).filter_by(name=p["team"]).first()
                    if not team:
                        team = Team(name=p["team"], country="???", league="Unknown", attack=1.0, defense=1.0)
                        session.add(team)
                        session.flush()

                    # c. Crear registro de estadísticas para la temporada actual
                    stats = session.query(PlayerSeasonStats).filter_by(
                        player_id=player.id, 
                        season=current_season
                    ).first()
                    
                    if not stats:
                        new_stats = PlayerSeasonStats(
                            player_id=player.id,
                            team_id=team.id,
                            season=current_season,
                            matches_played=p.get("matches_played", 0),
                            goals=p.get("goals", 0),
                            assists=p.get("assists", 0),
                            xG=p.get("xG", 0.0),
                            rating=p.get("rating", 0.0)
                        )
                        session.add(new_stats)
        session.commit()
        print(f"✅ Jugadores y estadísticas ({current_season}) migrados.")

    try:
        session.commit()
        print("🎉 Migración temporal completada con éxito.")
    except Exception as e:
        session.rollback()
        print(f"❌ Error durante la migración: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate()
