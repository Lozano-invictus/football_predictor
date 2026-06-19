"""
predictor/hybrid_model.py
Modelo Híbrido Multivariable (Dixon-Coles + Plantilla + Elo + Fichajes).
Es el cerebro predictivo del sistema Champions 25/26.
"""
import numpy as np
from typing import Dict, Any, Optional, Tuple
from .dixon_coles import DixonColesModel
import config

class HybridModel(DixonColesModel):
    def __init__(self):
        super().__init__()
        self.weights = {
            "xg": 0.5,
            "form": 0.2,
            "squad": 0.2,
            "transfers": 0.1
        }

    def get_team_player_strength(self, team_id: int, season: str, session=None) -> float:
        """Calcula el rating promedio de la plantilla en una temporada."""
        # Import diferido para evitar ciclo: predictor -> data.database -> predictor
        from data.database import get_session as _get_session, PlayerSeasonStats
        local_session = session or _get_session()
        try:
            stats = local_session.query(PlayerSeasonStats).filter_by(team_id=team_id, season=season).all()
            if not stats:
                return 7.0  # Rating base neutral

            ratings = [s.rating_avg for s in stats if s.rating_avg and s.rating_avg > 0]
            return sum(ratings) / len(ratings) if ratings else 7.0
        finally:
            if not session:
                local_session.close()

    def calculate_hybrid_strength(self, team: Dict, season: str, session=None) -> float:
        """
        Calcula la fuerza final combinando 4 dimensiones.
        """
        # 1. xG (Poder Ofensivo/Defensivo)
        xg_strength = (team.get("attack", 1.0) - team.get("defense", 1.0)) + 1.0
        
        # 2. Forma Reciente (Elo y Momentum)
        elo_factor = (team.get("elo", 1500) / 1500)
        
        # 3. Fuerza de Plantilla (Ratings individuales)
        squad_strength = self.get_team_player_strength(team.get("id"), season, session) / 7.0
        
        # 4. Impacto de Fichajes (Simulado)
        transfer_boost = 1.0 + (team.get("transfer_rating", 0.0) * 0.1)

        # Combinación ponderada
        final_strength = (
            xg_strength * self.weights["xg"] +
            elo_factor * self.weights["form"] +
            squad_strength * self.weights["squad"] +
            transfer_boost * self.weights["transfers"]
        )
        return round(final_strength, 3)

    def predict_hybrid(self, home: Dict, away: Dict, season: str) -> Dict:
        """Predicción completa usando el motor híbrido."""
        s1 = self.calculate_hybrid_strength(home, season)
        s2 = self.calculate_hybrid_strength(away, season)
        
        # Obtener los lambdas originales del modelo Dixon-Coles
        lh, la = self.expected_goals(home, away)
        
        # Ajustar los lambdas con la fuerza híbrida relativa
        lh_adj = lh * (s1 / s2)
        la_adj = la * (s2 / s1)
        
        # Generar matriz de probabilidades con lambdas ajustados
        matrix = self.score_matrix_custom(lh_adj, la_adj)
        
        home_win = float(np.tril(matrix, -1).sum())
        draw     = float(np.trace(matrix))
        away_win = float(np.triu(matrix,  1).sum())

        top_scores = []
        for i in range(min(6, self.max_goals + 1)):
            for j in range(min(6, self.max_goals + 1)):
                top_scores.append({
                    "home_goals": i,
                    "away_goals": j,
                    "score": f"{i}-{j}",
                    "probability": float(matrix[i, j]),
                })
        top_scores.sort(key=lambda x: x["probability"], reverse=True)

        return {
            "home_win":      home_win,
            "draw":          draw,
            "away_win":      away_win,
            "prob_home":     home_win,
            "prob_draw":     draw,
            "prob_away":     away_win,
            "expected_home": lh_adj,
            "expected_away": la_adj,
            "score_matrix":  matrix,
            "top_scores":    top_scores[:10],
            "hybrid_strength_home": s1,
            "hybrid_strength_away": s2,
            "model_type":    "Hybrid (Dixon-Coles + Squad + Elo)"
        }

    def predict_match(self, home: Dict, away: Dict, **kwargs) -> Dict:
        """
        Implementa el método abstracto predict_match de BaseFootballModel.
        Wrapper de predict_hybrid — ya devuelve la estructura estándar completa.
        """
        season = kwargs.get('season', '2024-25')
        # predict_hybrid ya retorna estructura completamente estandarizada
        return self.predict_hybrid(home, away, season)
        
    def score_matrix_custom(self, lh: float, la: float) -> np.ndarray:
        """Genera matriz de probabilidades para lambdas específicos."""
        from scipy.stats import poisson
        matrix = np.zeros((self.max_goals + 1, self.max_goals + 1))
        for x in range(self.max_goals + 1):
            for y in range(self.max_goals + 1):
                prob = poisson.pmf(x, lh) * poisson.pmf(y, la)
                correction = self._tau_correction(x, y, lh, la)
                matrix[x, y] = prob * correction
        return matrix / matrix.sum()
