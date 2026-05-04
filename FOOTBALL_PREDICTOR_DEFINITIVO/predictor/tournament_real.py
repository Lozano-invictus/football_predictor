"""
predictor/tournament_real.py
Simulador de Champions League Real por Rondas.
Simula desde Cuartos hasta la Final con el modelo Híbrido.
"""
import random
from typing import List, Dict, Any
from .hybrid_model import HybridModel

class RealTournamentSimulator:
    def __init__(self, season: str):
        self.model = HybridModel()
        self.season = season

    def simulate_match(self, t1: Dict, t2: Dict) -> Dict:
        """Simula un partido y devuelve el ganador."""
        res = self.model.predict_hybrid(t1, t2, self.season)
        # Probabilidades: win_t1, draw, win_t2
        probs = [res["home_win"], res["draw"], res["away_win"]]
        outcome = random.choices(["t1", "draw", "t2"], weights=probs)[0]
        
        if outcome == "draw":
            # Si hay empate, decidimos por penaltis (fuerza relativa)
            p1 = res["home_win"] / (res["home_win"] + res["away_win"]) if (res["home_win"] + res["away_win"]) > 0 else 0.5
            return t1 if random.random() < p1 else t2
        return t1 if outcome == "t1" else t2

    def simulate_round(self, teams: List[Dict]) -> List[Dict]:
        """Ejecuta una ronda eliminatoria."""
        winners = []
        # No barajamos aquí para mantener el cuadro si es necesario
        for i in range(0, len(teams), 2):
            if i + 1 < len(teams):
                winner = self.simulate_match(teams[i], teams[i+1])
                winners.append(winner)
            else:
                winners.append(teams[i])
        return winners

    def run_monte_carlo(self, teams: List[Dict], n_sims: int = 1000) -> Dict:
        """Simula el torneo miles de veces para obtener probabilidades."""
        champion_counts = {}
        reach_final_counts = {}
        reach_semi_counts = {}

        for _ in range(n_sims):
            current_teams = list(teams)
            
            # Cuartos
            current_teams = self.simulate_round(current_teams)
            for t in current_teams:
                reach_semi_counts[t["name"]] = reach_semi_counts.get(t["name"], 0) + 1
            
            # Semis
            current_teams = self.simulate_round(current_teams)
            for t in current_teams:
                reach_final_counts[t["name"]] = reach_final_counts.get(t["name"], 0) + 1
            
            # Final
            winner = self.simulate_match(current_teams[0], current_teams[1])
            champion_counts[winner["name"]] = champion_counts.get(winner["name"], 0) + 1

        # Normalizar resultados
        results = []
        for t in teams:
            name = t["name"]
            results.append({
                "name": name,
                "champion": champion_counts.get(name, 0) / n_sims,
                "final": reach_final_counts.get(name, 0) / n_sims,
                "semi": reach_semi_counts.get(name, 0) / n_sims
            })
        
        return sorted(results, key=lambda x: x["champion"], reverse=True)
