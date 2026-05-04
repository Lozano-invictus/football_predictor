"""
predictor/poisson_model.py
Modelo de distribución de Poisson para predicción de partidos.
Metodología basada en Dixon-Coles / TFG Olalquiaga 2023.
"""
import numpy as np
from scipy.stats import poisson
from typing import Dict, List, Tuple
import pandas as pd

from config import LEAGUE_AVG_GOALS, HOME_ADVANTAGE, MAX_GOALS
from .base_model import BaseFootballModel


class PoissonModel(BaseFootballModel):
    """
    Calcula probabilidades de resultado para un partido dado
    el team strength (ataque/defensa) de ambos equipos.

    Fórmula:
        λ_home = (att_home / avg) * (def_away / avg) * avg * home_adv
        λ_away = (att_away / avg) * (def_home / avg) * avg
    """

    def __init__(
        self,
        avg_goals: float = LEAGUE_AVG_GOALS,
        home_advantage: float = HOME_ADVANTAGE,
        max_goals: int = MAX_GOALS,
    ):
        self.avg = avg_goals
        self.home_adv = home_advantage
        self.max_goals = max_goals

    # ------------------------------------------------------------------ #
    # LAMBDAS
    # ------------------------------------------------------------------ #

    def expected_goals(
        self, home: Dict, away: Dict
    ) -> Tuple[float, float]:
        """Devuelve (λ_home, λ_away)."""
        lh = (home["attack"] / self.avg) * (away["defense"] / self.avg) * self.avg * self.home_adv
        la = (away["attack"] / self.avg) * (home["defense"] / self.avg) * self.avg
        return round(lh, 4), round(la, 4)

    # ------------------------------------------------------------------ #
    # MATRIZ DE PROBABILIDADES
    # ------------------------------------------------------------------ #

    def score_matrix(self, home: Dict, away: Dict) -> np.ndarray:
        """
        Matriz (max_goals+1 x max_goals+1) donde
        matrix[i][j] = P(home=i, away=j).
        """
        lh, la = self.expected_goals(home, away)
        goals = np.arange(self.max_goals + 1)
        ph = poisson.pmf(goals, lh)
        pa = poisson.pmf(goals, la)
        return np.outer(ph, pa)          # filas=local, columnas=visitante

    # ------------------------------------------------------------------ #
    # PROBABILIDADES GLOBALES
    # ------------------------------------------------------------------ #

    def match_probabilities(self, home: Dict, away: Dict) -> Dict:
        """
        Retorna dict con estructura ESTÁNDAR.
        """
        matrix = self.score_matrix(home, away)
        lh, la = self.expected_goals(home, away)

        home_win, draw, away_win = self._calculate_outcome_probabilities(matrix)
        top_scores = self._normalize_top_scores(matrix)

        return {
            "home_win": home_win,
            "draw": draw,
            "away_win": away_win,
            "expected_home": lh,
            "expected_away": la,
            "score_matrix": matrix,
            "top_scores": top_scores,
            "model_type": "Poisson",
        }

    # ------------------------------------------------------------------ #
    # ELIMINATORIA (ida + vuelta)
    # ------------------------------------------------------------------ #

    def two_leg_tie(
        self, home1: Dict, away1: Dict
    ) -> Dict:
        """
        Simula una eliminatoria a doble partido (ida en casa de home1).
        Devuelve probabilidades de clasificación tras 90' de cada partido.
        No modela prórroga ni penaltis — usa goles de visitante como desempate.
        """
        r1 = self.match_probabilities(home1, away1)   # ida
        r2 = self.match_probabilities(away1, home1)   # vuelta

        m1 = self.score_matrix(home1, away1)
        m2 = self.score_matrix(away1, home1)

        adv1 = 0.0   # clasificación equipo 1 (home en ida)
        adv2 = 0.0

        n = self.max_goals + 1
        for g1h in range(n):           # goles local en ida
            for g1a in range(n):       # goles visitante en ida
                p1 = m1[g1h, g1a]
                for g2h in range(n):   # goles local en vuelta (=away1)
                    for g2a in range(n):
                        p2 = m2[g2h, g2a]
                        p  = p1 * p2
                        # equipo1 total: g1h + g2a ; equipo2: g1a + g2h
                        t1 = g1h + g2a
                        t2 = g1a + g2h
                        if t1 > t2:
                            adv1 += p
                        elif t2 > t1:
                            adv2 += p
                        else:
                            # goles de visitante (away goals rule simplificada)
                            if g1a > g2a:        # equipo2 marcó más fuera
                                adv2 += p
                            elif g2a > g1a:
                                adv1 += p
                            else:
                                adv1 += p * 0.5  # cara o cruz
                                adv2 += p * 0.5

        total = adv1 + adv2
        return {
            "team1_qualify": adv1 / total if total > 0 else 0.5,
            "team2_qualify": adv2 / total if total > 0 else 0.5,
            "leg1": r1,
            "leg2": r2,
        }

    # ------------------------------------------------------------------ #
    # UTILIDAD: predict_points (igual que TFG)
    # ------------------------------------------------------------------ #

    def predict_points(self, home: Dict, away: Dict) -> Tuple[float, float]:
        """
        Retorna (pts_home, pts_away) en escala 0–3.
        Reproduce la función predict_points del TFG.
        """
        r = self.match_probabilities(home, away)
        pts_h = 3 * r["home_win"] + 1 * r["draw"]
        pts_a = 3 * r["away_win"] + 1 * r["draw"]
        return round(pts_h, 4), round(pts_a, 4)

    # ------------------------------------------------------------------ #
    # TABLA DE GRUPO
    # ------------------------------------------------------------------ #

    def simulate_group(self, teams: List[Dict]) -> pd.DataFrame:
        """
        Simula todos los partidos de un grupo round-robin (ida y vuelta).
        Devuelve DataFrame con Pos, Equipo, Pts, V, E, D, GF, GC, DG.
        """
        n = len(teams)
        records = {t["name"]: {"Pts": 0, "V": 0, "E": 0, "D": 0,
                                "GF": 0.0, "GC": 0.0} for t in teams}

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                h, a = teams[i], teams[j]
                ph, pa = self.predict_points(h, a)
                lh, la = self.expected_goals(h, a)

                records[h["name"]]["GF"] += lh
                records[h["name"]]["GC"] += la
                records[a["name"]]["GF"] += la
                records[a["name"]]["GC"] += lh

                if ph > pa:
                    records[h["name"]]["Pts"] += 3
                    records[h["name"]]["V"]   += 1
                    records[a["name"]]["D"]   += 1
                elif ph == pa:
                    records[h["name"]]["Pts"] += 1
                    records[a["name"]]["Pts"] += 1
                    records[h["name"]]["E"]   += 1
                    records[a["name"]]["E"]   += 1
                else:
                    records[a["name"]]["Pts"] += 3
                    records[a["name"]]["V"]   += 1
                    records[h["name"]]["D"]   += 1

        rows = []
        for t in teams:
            r = records[t["name"]]
            rows.append({
                "Equipo": t["name"],
                "Pts": r["Pts"],
                "V": r["V"], "E": r["E"], "D": r["D"],
                "GF": round(r["GF"], 1),
                "GC": round(r["GC"], 1),
                "DG": round(r["GF"] - r["GC"], 1),
            })

        df = pd.DataFrame(rows)
        df = df.sort_values(["Pts", "DG", "GF"], ascending=False).reset_index(drop=True)
        df.index += 1
        df.index.name = "Pos"
        return df
