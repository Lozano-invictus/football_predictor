"""
predictor/tournament.py
Simulador Monte Carlo de torneos eliminatorios (UCL-style).
"""
import random
import numpy as np
from typing import Dict, List, Tuple, Any, Union
from collections import defaultdict

from config import N_SIMULATIONS
from .poisson_model import PoissonModel


class TournamentSimulator:
    """
    Simula N veces un torneo eliminatorio de 8 equipos (cuartos → final)
    y devuelve las probabilidades de victoria para cada equipo.
    """

    def __init__(self, model: Union[PoissonModel, Any] = None,
                 n_simulations: int = N_SIMULATIONS):
        self.model = model or PoissonModel()
        self.n_sims = n_simulations

    # ------------------------------------------------------------------ #
    # PARTIDO INDIVIDUAL
    # ------------------------------------------------------------------ #

    def simulate_match(self, home: Dict, away: Dict,
                       neutral: bool = False) -> str:
        """
        Simula un partido único (sorteo aleatorio ponderado por Poisson).
        Devuelve el nombre del ganador. En caso de empate: cara o cruz.
        """
        lh, la = self.model.expected_goals(home, away)
        if neutral:
            # sin ventaja local
            la_adj = la / self.model.home_adv
            lh_adj = lh / self.model.home_adv
        else:
            lh_adj, la_adj = lh, la

        gh = np.random.poisson(lh_adj)
        ga = np.random.poisson(la_adj)

        if gh > ga:
            return home["name"]
        elif ga > gh:
            return away["name"]
        else:
            return random.choice([home["name"], away["name"]])

    # ------------------------------------------------------------------ #
    # ELIMINATORIA (ida + vuelta) — versión rápida
    # ------------------------------------------------------------------ #

    def simulate_tie(self, team1: Dict, team2: Dict) -> str:
        """Simula eliminatoria a doble partido. Devuelve clasificado."""
        gh1 = np.random.poisson(self.model.expected_goals(team1, team2)[0])
        ga1 = np.random.poisson(self.model.expected_goals(team1, team2)[1])
        gh2 = np.random.poisson(self.model.expected_goals(team2, team1)[0])
        ga2 = np.random.poisson(self.model.expected_goals(team2, team1)[1])

        t1_total = gh1 + ga2
        t2_total = ga1 + gh2

        if t1_total > t2_total:
            return team1["name"]
        elif t2_total > t1_total:
            return team2["name"]
        else:
            # regla del gol de visitante o cara-cruz
            if ga1 > ga2:
                return team2["name"]
            elif ga2 > ga1:
                return team1["name"]
            else:
                return random.choice([team1["name"], team2["name"]])

    # ------------------------------------------------------------------ #
    # FASE DE GRUPOS
    # ------------------------------------------------------------------ #

    def simulate_group_stage(
        self, groups: Dict[str, List[Dict]]
    ) -> Dict[str, List[str]]:
        """
        groups = {"A": [t1,t2,t3,t4], "B": [...], ...}
        Devuelve {"A": ["1º", "2º"], "B": [...], ...}
        """
        result = {}
        for group_name, teams in groups.items():
            standings = defaultdict(lambda: {"pts": 0, "gd": 0.0, "gf": 0.0})
            for i, h in enumerate(teams):
                for j, a in enumerate(teams):
                    if i == j:
                        continue
                    lh, la = self.model.expected_goals(h, a)
                    gh = np.random.poisson(lh)
                    ga = np.random.poisson(la)
                    standings[h["name"]]["gf"] += gh
                    standings[h["name"]]["gd"] += gh - ga
                    standings[a["name"]]["gd"] += ga - gh
                    standings[a["name"]]["gf"] += ga
                    if gh > ga:
                        standings[h["name"]]["pts"] += 3
                    elif gh == ga:
                        standings[h["name"]]["pts"] += 1
                        standings[a["name"]]["pts"] += 1
                    else:
                        standings[a["name"]]["pts"] += 3

            ranked = sorted(
                teams,
                key=lambda t: (
                    -standings[t["name"]]["pts"],
                    -standings[t["name"]]["gd"],
                    -standings[t["name"]]["gf"],
                ),
            )
            result[group_name] = [t["name"] for t in ranked]
        return result

    # ------------------------------------------------------------------ #
    # TORNEO ELIMINATORIO (cuartos → final)
    # ------------------------------------------------------------------ #

    def run_knockout(self, bracket: List[Tuple[Dict, Dict]],
                     use_two_legs: bool = True) -> str:
        """
        bracket: lista de pares (team1, team2).
        Simula rondas hasta obtener un campeón.
        """
        teams = list(bracket)
        while len(teams) > 1:
            next_round = []
            random.shuffle(teams)
            for i in range(0, len(teams), 2):
                t1_name, t2_name = teams[i], teams[i + 1]
                t1 = t1_name if isinstance(t1_name, dict) else {"name": t1_name}
                t2 = t2_name if isinstance(t2_name, dict) else {"name": t2_name}
                # buscar datos completos si solo tenemos nombre
                winner = self.simulate_match(t1, t2, neutral=(i == 0 and len(teams) == 2))
                next_round.append(winner)
            teams = next_round
        return teams[0] if isinstance(teams[0], str) else teams[0]["name"]

    # ------------------------------------------------------------------ #
    # SIMULACIÓN COMPLETA Monte Carlo
    # ------------------------------------------------------------------ #

    def simulate_champion(self, teams: List[Dict]) -> Dict[str, float]:
        """
        Simula N torneos de eliminación directa con los equipos dados.
        Devuelve {nombre_equipo: probabilidad_de_ganar}.
        """
        wins = defaultdict(int)
        n = len(teams)

        for _ in range(self.n_sims):
            pool = teams.copy()
            random.shuffle(pool)
            while len(pool) > 1:
                next_pool = []
                for i in range(0, len(pool) - 1, 2):
                    winner_name = self.simulate_tie(pool[i], pool[i + 1])
                    winner = next(
                        (t for t in teams if t["name"] == winner_name),
                        pool[i],
                    )
                    next_pool.append(winner)
                if len(pool) % 2 == 1:          # bye si número impar
                    next_pool.append(pool[-1])
                pool = next_pool
            if pool:
                wins[pool[0]["name"]] += 1

        return {t["name"]: round(wins[t["name"]] / self.n_sims, 4)
                for t in teams}

    # ------------------------------------------------------------------ #
    # FASE DE GRUPOS + ELIMINATORIAS (pipeline completo)
    # ------------------------------------------------------------------ #

    def full_tournament(
        self,
        groups: Dict[str, List[Dict]],
        n_sims: int = 1000,
    ) -> Dict[str, float]:
        """
        Pipeline completo:
        1. Simula fase de grupos n_sims veces.
        2. Los 1º y 2º de cada grupo pasan a eliminatorias.
        3. Simula la fase eliminatoria.
        4. Devuelve {equipo: P(campeón)}.
        """
        wins = defaultdict(int)
        all_teams = [t for grp in groups.values() for t in grp]
        team_map = {t["name"]: t for t in all_teams}

        for _ in range(n_sims):
            # --- grupos ---
            group_results = self.simulate_group_stage(groups)
            qualified = []
            for ranked_names in group_results.values():
                qualified.append(team_map[ranked_names[0]])  # 1º
                qualified.append(team_map[ranked_names[1]])  # 2º

            # --- eliminatorias ---
            pool = qualified.copy()
            random.shuffle(pool)
            while len(pool) > 1:
                next_pool = []
                for i in range(0, len(pool) - 1, 2):
                    w_name = self.simulate_tie(pool[i], pool[i + 1])
                    w = team_map.get(w_name, pool[i])
                    next_pool.append(w)
                if len(pool) % 2 == 1:
                    next_pool.append(pool[-1])
                pool = next_pool
            if pool:
                wins[pool[0]["name"]] += 1

        total = sum(wins.values()) or 1
        return {t: round(wins[t] / total, 4) for t in wins}
