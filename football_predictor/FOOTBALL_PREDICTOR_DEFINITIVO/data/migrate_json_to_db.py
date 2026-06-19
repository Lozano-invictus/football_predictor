"""
data/migrate_json_to_db.py
Migra datos de teams.json y players.json a SQLite usando el ORM unificado.
Soporta modelo temporal multi-temporada.

Uso:
    python data/migrate_json_to_db.py
"""

import json
import os
import sys
from pathlib import Path

# Forzar UTF-8 en stdout para Windows (evita UnicodeEncodeError con cp1252)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.append(str(Path(__file__).parent.parent))

from data.database import init_db, get_session, Team, Player, PlayerSeasonStats
import config


def migrate():
    print("[INFO] Iniciando migracion multi-temporada (JSON -> SQLite)...")
    init_db()
    session = get_session()

    current_season = config.CURRENT_SEASON

    # ------------------------------------------------------------------
    # 1. Migrar Equipos
    # ------------------------------------------------------------------
    if os.path.exists(config.TEAMS_FILE):
        with open(config.TEAMS_FILE, "r", encoding="utf-8") as f:
            teams_data = json.load(f)

        for t in teams_data.get("teams", []):
            existing = session.query(Team).filter_by(name=t["name"]).first()
            if not existing:
                new_team = Team(
                    name=t["name"],
                    country=t.get("country", "???"),
                    league=t.get("league", "Unknown"),
                    # Columnas unificadas del ORM (existen tanto en ORM como en BD real)
                    attack=float(t.get("attack", 1.0)),
                    defense=float(t.get("defense", 1.0)),
                    elo=float(t.get("elo", 1500.0)),
                    ucl_titles=int(t.get("ucl_titles", 0)),
                    rank=int(t.get("rank", 999)),
                )
                session.add(new_team)

        session.commit()
        print("[OK] Equipos migrados.")
    else:
        print(f"[WARN] Archivo no encontrado: {config.TEAMS_FILE}")

    # ------------------------------------------------------------------
    # 2. Migrar Jugadores y Estadísticas de Temporada
    # ------------------------------------------------------------------
    if os.path.exists(config.PLAYERS_FILE):
        with open(config.PLAYERS_FILE, "r", encoding="utf-8") as f:
            players_data = json.load(f)

        # Secciones del JSON: players (delanteros), goalkeepers, defenders
        for pos_key in ("players", "goalkeepers", "defenders"):
            for p in players_data.get(pos_key, []):
                # --- Jugador maestro ---
                player = session.query(Player).filter_by(name=p["name"]).first()
                if not player:
                    player = Player(
                        name=p["name"],
                        # Usar position_main (campo canónico del ORM unificado)
                        position_main=p.get("position", pos_key),
                        # position también para compatibilidad con la BD real
                        position=p.get("position", pos_key),
                        is_active=True,
                    )
                    session.add(player)
                    session.flush()  # obtener ID antes del commit

                # --- Equipo asociado ---
                team_name = p.get("team", "Unknown")
                team = session.query(Team).filter_by(name=team_name).first()
                if not team:
                    team = Team(
                        name=team_name,
                        country="???",
                        league="Unknown",
                        attack=1.0,
                        defense=1.0,
                    )
                    session.add(team)
                    session.flush()

                # --- Estadísticas de temporada ---
                stats = session.query(PlayerSeasonStats).filter_by(
                    player_id=player.id,
                    season=current_season,
                ).first()

                if not stats:
                    new_stats = PlayerSeasonStats(
                        player_id=player.id,
                        team_id=team.id,
                        season=current_season,
                        matches_played=int(p.get("matches_played", 0)),
                        goals=int(p.get("goals", 0)),
                        assists=int(p.get("assists", 0)),
                        # Usar nombres canónicos del ORM unificado
                        expected_goals=float(p.get("xG", p.get("expected_goals", 0.0))),
                        xG=float(p.get("xG", p.get("expected_goals", 0.0))),
                        rating_avg=float(p.get("rating", p.get("rating_avg", 0.0))),
                        rating=float(p.get("rating", p.get("rating_avg", 0.0))),
                        minutes_played=int(p.get("minutes", p.get("minutes_played", 0))),
                        minutes=int(p.get("minutes", p.get("minutes_played", 0))),
                        position=p.get("position", pos_key),
                        is_current_squad=True,
                    )
                    session.add(new_stats)

        session.commit()
        print(f"[OK] Jugadores y estadisticas ({current_season}) migrados.")
    else:
        print(f"[WARN] Archivo no encontrado: {config.PLAYERS_FILE}")

    try:
        session.commit()
        print("[OK] Migracion temporal completada con exito.")
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Error durante la migracion: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    migrate()
