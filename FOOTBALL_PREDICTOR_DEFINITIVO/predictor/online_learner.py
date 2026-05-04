"""
predictor/online_learner.py
Módulo de Online Learning para actualización dinámica del modelo tras cada partido.
Implementa recalibración de lambdas basada en resultados reales.
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, Tuple
from data.database import get_session, Team, Prediction
import config
from utils import logger

class OnlineLearner:
    def __init__(self, learning_rate: float = 0.05):
        self.lr = learning_rate

    def update_team_params(self, team_name: str, actual_goals: int, expected_goals: float, is_attack: bool = True):
        """
        Ajusta los parámetros de ataque o defensa basados en el error de predicción.
        Si anotó más de lo esperado -> ataque sube.
        Si recibió más de lo esperado -> defensa baja (valor sube).
        """
        session = get_session()
        team = session.query(Team).filter_by(name=team_name).first()
        
        if not team:
            return

        error = actual_goals - expected_goals
        
        if is_attack:
            # Ajustar ataque: attack_new = attack_old + lr * error
            team.attack = max(config.MIN_TEAM_ATTACK, min(config.MAX_TEAM_ATTACK, team.attack + self.lr * error))
        else:
            # Ajustar defensa: defense_new = defense_old + lr * (-error) 
            # (Si error es positivo, recibió más goles, la defensa empeora -> valor sube)
            team.defense = max(0.5, min(3.0, team.defense + self.lr * (actual_goals - expected_goals)))
        
        team.last_updated = datetime.utcnow()
        session.commit()
        session.close()
        logger.info(f"Online Learning: Parámetros actualizados para {team_name}")

    def process_match_result(self, match_data: Dict[str, Any]):
        """
        match_data: {
            'home_team': str, 'away_team': str, 
            'home_score': int, 'away_score': int,
            'exp_home': float, 'exp_away': float
        }
        """
        # Actualizar ataque Local y defensa Visitante
        self.update_team_params(match_data['home_team'], match_data['home_score'], match_data['exp_home'], is_attack=True)
        self.update_team_params(match_data['away_team'], match_data['home_score'], match_data['exp_home'], is_attack=False)
        
        # Actualizar ataque Visitante y defensa Local
        self.update_team_params(match_data['away_team'], match_data['away_score'], match_data['exp_away'], is_attack=True)
        self.update_team_params(match_data['home_team'], match_data['away_score'], match_data['exp_away'], is_attack=False)
