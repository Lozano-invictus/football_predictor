"""
predictor/base_model.py
Interfaz base para todos los modelos predictivos.
Asegura consistencia en las respuestas entre Poisson, Dixon-Coles, Hybrid, etc.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any
import numpy as np


class BaseFootballModel(ABC):
    """
    Interfaz base para todos los modelos de predicción.
    Define la estructura consistente que deben seguir todas las implementaciones.
    """

    @abstractmethod
    def predict_match(self, home: Dict, away: Dict, **kwargs) -> Dict:
        """
        Predice probabilidades de resultado para un partido.
        
        Args:
            home: Dict con datos del equipo local
            away: Dict con datos del equipo visitante
            **kwargs: Parámetros específicos del modelo
            
        Returns:
            Dict con estructura estandarizada:
            {
                "home_win": float (0-1),
                "draw": float (0-1),
                "away_win": float (0-1),
                "expected_home": float (goles esperados),
                "expected_away": float (goles esperados),
                "top_scores": [
                    {
                        "score": str ("2-1"),
                        "probability": float (0-1),
                        "home_goals": int,
                        "away_goals": int
                    },
                    ...
                ],
                "model_type": str ("Poisson" | "Dixon-Coles" | "Hybrid"),
                "confidence": float (0-1, optional)
            }
        """
        pass

    def _normalize_top_scores(self, matrix: np.ndarray, max_display: int = 10) -> List[Dict]:
        """
        Convierte matriz de probabilidades a formato estándar de top_scores.
        
        Args:
            matrix: ndarray de probabilidades (max_goals+1 x max_goals+1)
            max_display: Número máximo de marcadores a retornar
            
        Returns:
            Lista de dicts con score, probability, home_goals, away_goals
        """
        scores = []
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                scores.append({
                    "score": f"{i}-{j}",
                    "probability": float(matrix[i, j]),
                    "home_goals": i,
                    "away_goals": j
                })
        scores.sort(key=lambda x: x["probability"], reverse=True)
        return scores[:max_display]

    def _calculate_outcome_probabilities(self, matrix: np.ndarray) -> tuple:
        """
        Calcula probabilidades de victoria local, empate y victoria visitante.
        
        Returns:
            (home_win, draw, away_win) - Tupla con probabilidades normalizadas
        """
        home_win = float(np.tril(matrix, -1).sum())
        draw = float(np.trace(matrix))
        away_win = float(np.triu(matrix, 1).sum())
        
        total = home_win + draw + away_win
        if total == 0:
            return 0.33, 0.34, 0.33
        
        return home_win / total, draw / total, away_win / total
