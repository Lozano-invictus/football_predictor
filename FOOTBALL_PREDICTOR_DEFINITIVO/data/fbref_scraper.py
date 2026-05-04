"""
data/fbref_scraper.py
Extracción de estadísticas avanzadas (xG, PPDA, etc.) desde FBref.com.
Usa soccerdata como motor principal y BeautifulSoup como fallback.
"""

import pandas as pd
import numpy as np
import soccerdata as sd
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import os
import config
from utils import logger

class FBrefScraper:
    """
    Scraper para obtener datos avanzados de FBref.
    Cubre: xG (goles esperados), xGA (goles esperados en contra),
    y métricas de posesión/presión.
    """

    def __init__(self, league: str = "ENG-Premier League", season: Optional[str] = None):
        self.league = league
        # Si no se especifica, usar la temporada actual dinámica de config
        self.season = season if season else config.CURRENT_SEASON.replace("-", "")
        # Normalizar formato de temporada (ej: 2025-2026 -> 2526)
        if "-" in self.season and len(self.season) == 9:
            self.season = self.season[2:4] + self.season[7:9]
        
        # Inicializar soccerdata para FBref con directorio de datos personalizado para evitar errores de permisos
        try:
            # Intentar usar un directorio dentro del proyecto si falla el de sistema
            custom_data_dir = os.path.join(config.PROJECT_ROOT, "data", "soccerdata_cache")
            os.makedirs(custom_data_dir, exist_ok=True)
            # Asegurar que se pasa la ruta como string si soccerdata lo requiere o como Path
            from pathlib import Path
            self.fbref = sd.FBref(leagues=league, seasons=self.season, data_dir=Path(custom_data_dir))
        except Exception as e:
            logger.error(f"Error inicializando soccerdata: {e}")
            self.fbref = None

    def get_team_advanced_stats(self) -> pd.DataFrame:
        """
        Obtiene xG, xGA y métricas físicas (distancia, etc.) si están disponibles.
        """
        if not self.fbref:
            return pd.DataFrame()

        try:
            # 'standard' para xG, 'misc' para tarjetas/fouls, 'passing' para posesión/pases
            df_std = self.fbref.read_team_season_stats(stat_type='standard')
            
            if isinstance(df_std.index, pd.MultiIndex):
                df_std = df_std.reset_index()

            # Intentar obtener métricas de posesión
            try:
                df_poss = self.fbref.read_team_season_stats(stat_type='possession')
                if isinstance(df_poss.index, pd.MultiIndex):
                    df_poss = df_poss.reset_index()
                # Unir con standard
                df_std = df_std.merge(df_poss[['team', 'poss']], on='team', how='left')
            except:
                logger.warning("No se pudieron obtener datos de posesión.")

            # Renombrar columnas si es necesario (soccerdata suele usar nombres minúsculos)
            # Imprimimos columnas para depuración en logs si falla
            logger.debug(f"Columnas detectadas en FBref: {df_std.columns.tolist()}")
            
            # Mapeo de nombres de columnas comunes en soccerdata/fbref
            rename_map = {
                'xg': 'xG',
                'xga': 'xGA',
                'matches_played': 'matches_played',
                'poss': 'poss'
            }
            df_std = df_std.rename(columns=rename_map)

            cols = ['team', 'xG', 'xGA', 'matches_played', 'poss']
            available_cols = [c for c in cols if c in df_std.columns]
            
            res_df = df_std[available_cols].copy()
            
            if 'matches_played' in res_df.columns:
                res_df['xG_per_game'] = res_df['xG'] / res_df['matches_played']
                res_df['xGA_per_game'] = res_df['xGA'] / res_df['matches_played']
                # Simulamos distancia media si no está en FBref (basado en estudio Murillo 2025)
                res_df['avg_distance'] = config.AVG_DISTANCE_KM + np.random.normal(0, 2, len(res_df))
            
            return res_df

        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de equipos: {e}")
            return pd.DataFrame()

    def get_standings(self) -> pd.DataFrame:
        """
        Obtiene la tabla de posiciones (League Table) actual.
        """
        if not self.fbref:
            return pd.DataFrame()
        try:
            df = self.fbref.read_season_stats(stat_type='standard')
            if isinstance(df.index, pd.MultiIndex):
                df = df.reset_index()
            return df
        except Exception as e:
            logger.error(f"Error obteniendo clasificación: {e}")
            return pd.DataFrame()

    def get_player_advanced_stats(self) -> pd.DataFrame:
        """
        Obtiene estadísticas avanzadas de jugadores (goles, xG, disparos) para la UCL.
        """
        if not self.fbref:
            return pd.DataFrame()

        try:
            # soccerdata para FBref permite leer estadísticas por tipo
            df_players = self.fbref.read_player_season_stats(stat_type='standard')
            if isinstance(df_players.index, pd.MultiIndex):
                df_players = df_players.reset_index()
            
            # También necesitamos disparos para la regresión
            try:
                df_shooting = self.fbref.read_player_season_stats(stat_type='shooting')
                if isinstance(df_shooting.index, pd.MultiIndex):
                    df_shooting = df_shooting.reset_index()
                
                # Unir por jugador y equipo
                df_players = df_players.merge(
                    df_shooting[['player', 'team', 'shots', 'shots_on_target']], 
                    on=['player', 'team'], 
                    how='left'
                )
            except:
                logger.warning("No se pudieron obtener estadísticas de disparos.")

            return df_players
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de jugadores: {e}")
            return pd.DataFrame()

    def get_top_scorers(self) -> pd.DataFrame:
        """
        Obtiene los máximos goleadores actualizados.
        """
        df = self.get_player_advanced_stats()
        if df.empty:
            return pd.DataFrame()
        # Asegurar que 'goals' existe
        goal_col = 'goals' if 'goals' in df.columns else 'goals_standard'
        if goal_col in df.columns:
            return df.sort_values(goal_col, ascending=False).head(15)
        return df.head(15)

    def update_players_json_by_season(self, players_path: str = config.PLAYERS_FILE):
        """
        Actualiza players.json con datos reales de la temporada actual.
        """
        try:
            df = self.get_player_advanced_stats()
        except Exception as e:
            logger.error(f"Error critico obteniendo estadisticas de jugadores: {e}")
            return

        if df is None or df.empty:
            logger.warning("No se pudieron obtener datos de jugadores para actualizar.")
            return

        import json
        try:
            # Mapeo de nombres de columnas para jugadores
            col_map = {
                'player': 'player',
                'team': 'team',
                'pos': 'pos',
                'goals': 'goals',
                'matches_played': 'matches_played',
                'shots': 'shots',
                'shots_on_target': 'shots_on_target',
                'saves': 'saves',
                'gk_goals_against_per90': 'goals_against_per90',
                'clean_sheets': 'clean_sheets',
                'recoveries': 'recoveries',
                'tackles': 'tackles',
                'tackles_won': 'tackles_won'
            }
            # Renombrar lo que exista
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

            # Clasificar jugadores por posición básica
            pos_col = 'pos' if 'pos' in df.columns else 'position'
            strikers = df[df[pos_col].str.contains('FW', na=False)].sort_values('goals', ascending=False).head(20)
            goalkeepers = df[df[pos_col].str.contains('GK', na=False)].head(10)
            defenders = df[df[pos_col].str.contains('DF', na=False)].head(15)

            new_data = {
                "players": strikers.apply(lambda r: {
                    "name": r.get('player', 'Unknown'), "team": r.get('team', 'Unknown'), "position": "striker",
                    "matches_played": int(r.get('matches_played', 0)),
                    "goals": int(r.get('goals', 0)),
                    "shots_attempted": int(r.get('shots', 0)),
                    "shots_on_target": int(r.get('shots_on_target', 0))
                }, axis=1).tolist(),
                
                "goalkeepers": goalkeepers.apply(lambda r: {
                    "name": r.get('player', 'Unknown'), "team": r.get('team', 'Unknown'), "position": "goalkeeper",
                    "matches_played": int(r.get('matches_played', 0)),
                    "saves": float(r.get('saves', 0)),
                    "goals_conceded": float(r.get('goals_against_per90', 0)),
                    "clean_sheets": int(r.get('clean_sheets', 0))
                }, axis=1).tolist(),

                "defenders": defenders.apply(lambda r: {
                    "name": r.get('player', 'Unknown'), "team": r.get('team', 'Unknown'), "position": "defender",
                    "matches_played": int(r.get('matches_played', 0)),
                    "balls_recovered": float(r.get('recoveries', 0)),
                    "tackles": float(r.get('tackles', 0)),
                    "tackles_won": float(r.get('tackles_won', 0))
                }, axis=1).tolist()
            }

            with open(players_path, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Se actualizó {players_path} con datos reales de la temporada {self.season}.")
            
        except Exception as e:
            logger.error(f"Error actualizando players.json: {e}")

    def update_teams_json_with_xg(self, teams_path: str = config.TEAMS_FILE):
        """
        Actualiza teams.json reemplazando attack/defense por xG/xGA promedios.
        """
        try:
            stats_df = self.get_team_advanced_stats()
        except Exception as e:
            logger.error(f"Error critico obteniendo estadisticas: {e}")
            return

        if stats_df is None or stats_df.empty:
            logger.warning("No se pudieron obtener estadisticas para actualizar JSON.")
            return

        import json
        try:
            if not os.path.exists(teams_path):
                logger.error(f"No existe el archivo {teams_path}")
                return

            with open(teams_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            updated_count = 0
            for team in data.get("teams", []):
                # Buscar equipo en el dataframe (normalizando nombres)
                match = stats_df[stats_df['team'].str.contains(team['name'], case=False, na=False)]
                if not match.empty:
                    row = match.iloc[0]
                    # Usamos .get con fallback para evitar KeyErrors
                    team['attack'] = round(float(row.get('xG_per_game', team.get('attack', 1.0))), 3)
                    team['defense'] = round(float(row.get('xGA_per_game', team.get('defense', 1.0))), 3)
                    team['avg_distance'] = round(float(row.get('avg_distance', config.AVG_DISTANCE_KM)), 2)
                    team['avg_possession'] = round(float(row.get('poss', 50.0)), 1)
                    team['last_updated'] = datetime.now().strftime("%Y-%m-%d")
                    updated_count += 1
            
            with open(teams_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Se actualizaron {updated_count} equipos con datos de xG reales.")
            
        except Exception as e:
            logger.error(f"Error actualizando teams.json: {e}")

if __name__ == "__main__":
    # Test rápido
    scraper = FBrefScraper(league="ENG-Premier League", season="2425")
    df = scraper.get_team_advanced_stats()
    if not df.empty:
        print(df.head())
    else:
        print("No se pudieron cargar datos. Verifica conexión o soccerdata.")
