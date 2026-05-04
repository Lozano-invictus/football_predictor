"""
predictor/dixon_coles.py
Implementación del modelo Dixon-Coles para predicción de fútbol.
Corrige la subestimación de empates y marcadores bajos del modelo de Poisson.
Incluye factor de decaimiento temporal y racha de forma reciente.
"""

import numpy as np
from scipy.stats import poisson
from typing import Dict, List, Tuple, Optional
import pandas as pd
from datetime import datetime

from config import LEAGUE_AVG_GOALS, HOME_ADVANTAGE, MAX_GOALS, RHO_CORRECTION, TIME_DECAY_XI
from .base_model import BaseFootballModel


class DixonColesModel(BaseFootballModel):
    """
    Modelo Dixon-Coles:
    1. Ajusta probabilidades de marcadores {0,0}, {1,0}, {0,1}, {1,1} mediante factor rho.
    2. Incorpora decaimiento temporal (opcional en el cálculo de lambdas).
    3. Interfaz compatible con PoissonModel.
    """

    def __init__(
        self,
        avg_goals: float = LEAGUE_AVG_GOALS,
        home_advantage: float = HOME_ADVANTAGE,
        max_goals: int = MAX_GOALS,
        rho: float = -0.15,  # Valor típico de correlación para fútbol
    ):
        self.avg = avg_goals
        self.home_adv = home_advantage
        self.max_goals = max_goals
        self.rho = rho

    def _tau_correction(self, x: int, y: int, lh: float, la: float) -> float:
        """
        Función de corrección tau para marcadores bajos.
        Dixon and Coles (1997).
        """
        if not RHO_CORRECTION:
            return 1.0
            
        if x == 0 and y == 0:
            return 1 - (lh * la * self.rho)
        elif x == 0 and y == 1:
            return 1 + (lh * self.rho)
        elif x == 1 and y == 0:
            return 1 + (la * self.rho)
        elif x == 1 and y == 1:
            return 1 - self.rho
        else:
            return 1.0

    def expected_goals(
        self, home: Dict, away: Dict, home_form: float = 1.0, away_form: float = 1.0
    ) -> Tuple[float, float]:
        """
        Calcula lambdas considerando ataque, defensa, ventaja local y forma reciente.
        forma: multiplicador (ej: 1.1 para buena racha, 0.9 para mala).
        """
        lh = (home["attack"] / self.avg) * (away["defense"] / self.avg) * self.avg * self.home_adv * home_form
        la = (away["attack"] / self.avg) * (home["defense"] / self.avg) * self.avg * away_form
        return round(lh, 4), round(la, 4)

    def score_matrix(self, home: Dict, away: Dict, home_form: float = 1.0, away_form: float = 1.0) -> np.ndarray:
        """
        Genera matriz de probabilidades con corrección Dixon-Coles.
        """
        lh, la = self.expected_goals(home, away, home_form, away_form)
        
        matrix = np.zeros((self.max_goals + 1, self.max_goals + 1))
        
        for x in range(self.max_goals + 1):
            for y in range(self.max_goals + 1):
                prob = poisson.pmf(x, lh) * poisson.pmf(y, la)
                correction = self._tau_correction(x, y, lh, la)
                matrix[x, y] = prob * correction
        
        # Normalizar para asegurar que sume 1 (debido a la corrección tau y truncamiento)
        return matrix / matrix.sum()

    def match_probabilities(self, home: Dict, away: Dict, home_form: float = 1.0, away_form: float = 1.0) -> Dict:
        """
        Interfaz compatible con PoissonModel.
        """
        matrix = self.score_matrix(home, away, home_form, away_form)
        lh, la = self.expected_goals(home, away, home_form, away_form)

        home_win = float(np.tril(matrix, -1).sum())
        draw     = float(np.trace(matrix))
        away_win = float(np.triu(matrix,  1).sum())

        top_scores = []
        for i in range(min(6, self.max_goals + 1)):
            for j in range(min(6, self.max_goals + 1)):
                top_scores.append({
                    "home_goals": i,
                    "away_goals": j,
                    "probability": float(matrix[i, j]),
                })
        top_scores.sort(key=lambda x: x["probability"], reverse=True)

        return {
            "home_win":      home_win,
            "draw":          draw,
            "away_win":      away_win,
            "expected_home": lh,
            "expected_away": la,
            "score_matrix":  matrix,
            "top_scores":    top_scores[:10],
            "model_type":    "Dixon-Coles"
        }

    def predict_points(self, home: Dict, away: Dict, home_form: float = 1.0, away_form: float = 1.0) -> Tuple[float, float]:
        """Puntos esperados (0-3)."""
        r = self.match_probabilities(home, away, home_form, away_form)
        pts_h = 3 * r["home_win"] + 1 * r["draw"]
        pts_a = 3 * r["away_win"] + 1 * r["draw"]
        return round(pts_h, 4), round(pts_a, 4)
