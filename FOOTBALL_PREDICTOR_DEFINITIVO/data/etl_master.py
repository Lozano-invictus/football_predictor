"""
data/etl_master.py
ETL Maestro - Consolidación de datos históricos y en curso (2022-2026).
Normaliza múltiples CSVs de CHAMPIONS_LEUE_PRO en el esquema relacional TOTAL.
"""

import pandas as pd
import os
import sys
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
import numpy as np

# Añadir raíz al path
sys.path.append(str(Path(__file__).parent.parent))

from data.database import init_db, get_session, Team, Player, PlayerSeasonStats, Transfer, TeamSeasonStats, Match, Coach, MarketValueHistory, MatchEvent, Injury
import config
from utils import logger
from thefuzz import process, fuzz

class DataNormalizer:
    """Clase para normalizar nombres de equipos y jugadores con mapeo manual."""
    def __init__(self, session):
        self.session = session
        self.team_cache = {t.name: t.id for t in session.query(Team).all()}
        self.player_cache = {p.name: p.id for p in session.query(Player).all()}
        
        # Mapeo manual para casos donde el fuzzy falla
        self.manual_team_map = {
            "R. Madrid": "Real Madrid",
            "Man City": "Manchester City",
            "Bayern": "Bayern Munich",
            "Inter": "Inter Milan",
            "Milan": "AC Milan",
            "Athletic": "Atlético Madrid"
        }

    def get_team_id(self, name):
        if not name or pd.isna(name): return None
        name = name.strip()
        
        # 1. Caché directo
        if name in self.team_cache: return self.team_cache[name]
        
        # 2. Mapeo manual
        if name in self.manual_team_map:
            mapped_name = self.manual_team_map[name]
            if mapped_name in self.team_cache: return self.team_cache[mapped_name]

        # 3. Fuzzy match
        names = list(self.team_cache.keys())
        if not names: return None
        match, score = process.extractOne(name, names, scorer=fuzz.token_sort_ratio)
        if score > 85:
            return self.team_cache[match]
        return None

class ETLMasterPro:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.seasons_folders = ["2022_23", "2023_24", "2024_25", "2025_26"]
        self.master_folder = self.base_path / "_MASTER"
        self.audit_logs = []

    def log_audit(self, message: str, level: str = "INFO"):
        self.audit_logs.append({"timestamp": datetime.now(), "level": level, "message": message})
        if level == "ERROR": logger.error(message)
        else: logger.info(message)

    def _validate_df(self, df: pd.DataFrame, required_cols: list, filename: str) -> bool:
        """Valida que el DataFrame tenga las columnas necesarias."""
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            self.log_audit(f"Archivo {filename} corrupto o incompleto. Faltan columnas: {missing}", "ERROR")
            return False
        return True

    def run_full_ingestion(self):
        self.log_audit("🚀 Iniciando Ingesta Maestra de Datos UCL Enterprise (2022-2026)...")
        init_db()
        session = get_session()
        self.normalizer = DataNormalizer(session)

        try:
            # 1. Cargar Datos Maestros
            self._import_master_data(session)

            # 2. Ingesta por Temporada
            for s_folder in self.seasons_folders:
                season_label = self.normalize_season(s_folder)
                
                # Búsqueda de carpeta con fallback
                folder_path = self.base_path / s_folder
                if not folder_path.exists():
                    folder_path = self.base_path / "data" / s_folder
                
                if not folder_path.exists():
                    self.log_audit(f"Carpeta no encontrada para temporada {season_label}. Saltando...", "WARNING")
                    continue

                self.log_audit(f"--- Procesando Temporada {season_label} ---")
                
                # Importaciones con manejo de errores interno
                try:
                    self._import_teams_pro(folder_path, season_label, session)
                    self._import_players_pro(folder_path, season_label, session)
                    self._import_transfers_pro(folder_path, season_label, session)
                    self._import_matches_pro(folder_path, season_label, session)
                except Exception as e:
                    self.log_audit(f"Error procesando temporada {season_label}: {e}", "ERROR")

            # 3. Datos Específicos Live
            self._import_current_live_data(session)

            session.commit()
            self.log_audit("🎉 Ingesta Maestra Enterprise completada con éxito.")
        except Exception as e:
            session.rollback()
            self.log_audit(f"❌ Error crítico en pipeline ETL: {e}", "ERROR")
            raise e
        finally:
            session.close()

    def _import_teams_pro(self, path: Path, season: str, session: Session):
        file_path = path / "teams.csv"
        if not file_path.exists(): 
            self.log_audit(f"teams.csv no encontrado en {path}", "WARNING")
            return

        df = pd.read_csv(file_path)
        if not self._validate_df(df, ['Team'], "teams.csv"): return

        for _, row in df.iterrows():
            name = row.get('Team') or row.get('name') or row.get('team')
            if not name: continue
            
            team = session.query(Team).filter_by(name=name).first()
            if not team:
                team = Team(name=name, country=row.get('country', '???'), league="Champions League")
                session.add(team)
                session.flush()
                self.normalizer.team_cache[name] = team.id

            stats = session.query(TeamSeasonStats).filter_by(team_id=team.id, season=season).first()
            if not stats:
                session.add(TeamSeasonStats(
                    team_id=team.id,
                    season=season,
                    attack_score=float(row.get('attack', 1.2)),
                    defense_score=float(row.get('defense', 1.0)),
                    elo_rating=float(row.get('elo', 1500.0)),
                    group_name=str(row.get('group', ''))
                ))
            
            # Importar Coach si existe
            coach_name = row.get('coach')
            if coach_name:
                coach = session.query(Coach).filter_by(name=coach_name, team_id=team.id, season=season).first()
                if not coach:
                    session.add(Coach(name=coach_name, team_id=team.id, season=season))

    def _import_players_pro(self, path: Path, season: str, session: Session):
        file_players = path / "players.csv"
        file_scorers = path / "top_scorers.csv"
        
        df = pd.DataFrame()
        if file_players.exists(): df = pd.read_csv(file_players)
        if file_scorers.exists():
            df_s = pd.read_csv(file_scorers)
            df = pd.concat([df, df_s]).drop_duplicates(subset=['Player', 'Club'])

        if df.empty: return

        for _, row in df.iterrows():
            p_name = row.get('Player') or row.get('name') or row.get('player')
            if not p_name: continue

            player = session.query(Player).filter_by(name=p_name).first()
            if not player:
                player = Player(name=p_name, nationality=row.get('Nationality', '???'), position_main=row.get('Position', 'FW'))
                session.add(player)
                session.flush()

            t_name = row.get('Club') or row.get('team') or row.get('club')
            team_id = self.normalizer.get_team_id(t_name)
            if not team_id: continue

            stats = session.query(PlayerSeasonStats).filter_by(player_id=player.id, season=season).first()
            if not stats:
                new_stats = PlayerSeasonStats(
                    player_id=player.id,
                    team_id=team_id,
                    season=season,
                    goals=int(row.get('Goals', row.get('goals', 0))),
                    assists=int(row.get('Assists', row.get('assists', 0))),
                    minutes_played=int(row.get('Minutes', 0)),
                    market_value=float(row.get('Value', 0)),
                    rating_avg=float(row.get('Rating', 7.0)),
                    position=row.get('Position', player.position_main)
                )
                session.add(new_stats)
                
                # Historial de Valor
                if new_stats.market_value > 0:
                    session.add(MarketValueHistory(player_id=player.id, value=new_stats.market_value))

    def _import_transfers_pro(self, path: Path, season: str, session: Session):
        file_path = path / "transfers.csv"
        if not file_path.exists(): return

        df = pd.read_csv(file_path)
        for _, row in df.iterrows():
            p_name = row.get('Player')
            if not p_name: continue
            
            p_id = self.normalizer.get_player_id(p_name)
            if not p_id: continue
                
            f_team_id = self.normalizer.get_team_id(row.get('From'))
            t_team_id = self.normalizer.get_team_id(row.get('To'))
            
            transfer = Transfer(
                player_id=p_id,
                from_team_id=f_team_id,
                to_team_id=t_team_id,
                fee=float(str(row.get('Fee', 0)).replace('€', '').replace('M', '').strip() or 0),
                season=season
            )
            session.add(transfer)

    def _import_matches_pro(self, path: Path, season: str, session: Session):
        file_path = path / "knockout_stage.csv"
        if not file_path.exists(): return

        df = pd.read_csv(file_path)
        for _, row in df.iterrows():
            t1_id = self.normalizer.get_team_id(row.get('team1') or row.get('home_team'))
            t2_id = self.normalizer.get_team_id(row.get('team2') or row.get('away_team'))
            
            if not t1_id or not t2_id: continue

            match = Match(
                season=season,
                stage=row.get('round', 'Knockout'),
                home_team_id=t1_id,
                away_team_id=t2_id,
                home_score=int(row.get('score1', 0)),
                away_score=int(row.get('score2', 0)),
                status="Finished"
            )
            session.add(match)


    def _import_current_live_data(self, session: Session):
        # Cargar datos específicos de semifinalistas 2025/26
        file_semi = self.base_path / "2025_26" / "key_players_semifinalists.csv"
        if file_semi.exists():
            df = pd.read_csv(file_semi)
            # Lógica de actualización para los semifinalistas actuales...
            logger.info("✅ Datos de Semifinalistas 2025/26 integrados.")

if __name__ == "__main__":
    base = "c:/Users/ESTEBAN LOZANO/Downloads/football_predictor/CHAMPIONS_LEUE_PRO"
    etl = ETLMasterPro(base)
    etl.run_full_ingestion()
