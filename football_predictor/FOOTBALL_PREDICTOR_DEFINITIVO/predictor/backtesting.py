"""
predictor/backtesting.py
MÓDULO PROFESIONAL DE BACKTESTING DE MODELOS PREDICTIVOS DE FÚTBOL.
Calcula métricas de rendimiento y guarda resultados en BD.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, log_loss, brier_score_loss
)

from data.database import (
    get_session, Match, Team, BacktestResult
)
from predictor.poisson_model import PoissonModel
from predictor.dixon_coles import DixonColesModel
from predictor.hybrid_model import HybridModel
from utils import logger


class FootballBacktester:
    """Backtester profesional para modelos predictivos de fútbol."""

    MODEL_CLASSES = {
        "poisson": PoissonModel,
        "dixon_coles": DixonColesModel,
        "hybrid": HybridModel
    }

    def __init__(self):
        self.session = get_session()

    def _get_matches_for_season(self, season: str) -> List[Match]:
        """Obtiene partidos finalizados para una temporada."""
        matches = self.session.query(Match).filter(
            Match.season == season,
            Match.status == "FINISHED",
            Match.home_score.isnot(None),
            Match.away_score.isnot(None)
        ).order_by(Match.date).all()
        logger.info(f"Obtenidos {len(matches)} partidos para temporada {season}")
        return matches

    def _get_team_dict(self) -> Dict[int, Team]:
        """Crea diccionario de equipos para acceso rápido."""
        teams = self.session.query(Team).all()
        return {team.id: team for team in teams}

    def _get_actual_result(self, home_goals: int, away_goals: int) -> str:
        """Obtiene el resultado real: 'home', 'draw', 'away'."""
        if home_goals > away_goals:
            return "home"
        elif home_goals < away_goals:
            return "away"
        else:
            return "draw"

    def _calculate_brier_score(
        self,
        predicted_probs: Dict[str, float],
        actual_result: str
    ) -> float:
        """Calcula el Brier Score (medida de calibración)."""
        brier = 0.0
        for result in ["home", "draw", "away"]:
            predicted = predicted_probs.get(result, 0.0)
            actual = 1.0 if result == actual_result else 0.0
            brier += (predicted - actual) ** 2
        return brier / 3

    def run_backtest(
        self,
        model_name: str,
        season: str
    ) -> Dict[str, Any]:
        """
        Ejecuta el backtest completo para un modelo y temporada.
        Devuelve diccionario con todas las métricas.
        """
        logger.info(f"Iniciando backtest para modelo {model_name}, temporada {season}")

        if model_name not in self.MODEL_CLASSES:
            raise ValueError(f"Modelo {model_name} no reconocido")

        matches = self._get_matches_for_season(season)
        if len(matches) == 0:
            logger.warning(f"No hay partidos para temporada {season}")
            return {}

        team_dict = self._get_team_dict()
        model = self.MODEL_CLASSES[model_name]()

        y_true = []
        y_pred = []
        prob_distributions = []
        total_brier = 0.0

        for match in matches:
            try:
                home_team = team_dict.get(match.home_team_id)
                away_team = team_dict.get(match.away_team_id)

                if not home_team or not away_team:
                    logger.warning(f"Equipo no encontrado para partido {match.id}")
                    continue

                # Convertir equipos a diccionario para compatibilidad con modelos
                home_dict = {
                    "name": home_team.name,
                    "attack": home_team.attack,
                    "defense": home_team.defense,
                    "elo": home_team.elo
                }

                away_dict = {
                    "name": away_team.name,
                    "attack": away_team.attack,
                    "defense": away_team.defense,
                    "elo": away_team.elo
                }

                # Obtener predicción
                prediction = model.predict_match(home_dict, away_dict)

                # Obtener probabilidades
                prob_home = prediction.get("prob_home", 0.0)
                prob_draw = prediction.get("prob_draw", 0.0)
                prob_away = prediction.get("prob_away", 0.0)
                probs = {"home": prob_home, "draw": prob_draw, "away": prob_away}

                # Obtener resultado predicho (el de mayor probabilidad)
                pred_result = max(probs, key=probs.get)

                # Obtener resultado real
                true_result = self._get_actual_result(match.home_score, match.away_score)

                # Guardar para métricas
                y_true.append(true_result)
                y_pred.append(pred_result)
                prob_distributions.append([prob_home, prob_draw, prob_away])
                total_brier += self._calculate_brier_score(probs, true_result)

            except Exception as e:
                logger.error(f"Error procesando partido {match.id}: {e}")
                continue

        if len(y_true) == 0:
            logger.warning("No se pudieron procesar partidos para backtest")
            return {}

        # Calcular métricas
        metrics = self._calculate_metrics(
            y_true, y_pred, prob_distributions, total_brier, len(y_true)
        )
        metrics["model_name"] = model_name
        metrics["season"] = season
        metrics["matches_tested"] = len(y_true)

        logger.info(f"Backtest completado para {model_name} ({season})")
        return metrics

    def _calculate_metrics(
        self,
        y_true: List[str],
        y_pred: List[str],
        prob_distributions: List[List[float]],
        total_brier: float,
        n_matches: int
    ) -> Dict[str, float]:
        """Calcula todas las métricas de rendimiento."""
        # Convertir a números para scikit-learn
        label_map = {"home": 0, "draw": 1, "away": 2}
        y_true_num = [label_map[r] for r in y_true]
        y_pred_num = [label_map[r] for r in y_pred]

        # Métricas básicas
        accuracy = accuracy_score(y_true_num, y_pred_num)

        # Precision y Recall por clase
        precision = precision_score(
            y_true_num, y_pred_num, average=None, labels=[0, 1, 2], zero_division=0
        )
        recall = recall_score(
            y_true_num, y_pred_num, average=None, labels=[0, 1, 2], zero_division=0
        )

        f1 = f1_score(
            y_true_num, y_pred_num, average="weighted", zero_division=0
        )

        # Log Loss (necesita probabilidades)
        logloss = log_loss(
            y_true_num, np.array(prob_distributions), labels=[0,1,2]
        )

        avg_brier = total_brier / n_matches

        return {
            "accuracy": accuracy,
            "precision_home": precision[0],
            "precision_draw": precision[1],
            "precision_away": precision[2],
            "recall_home": recall[0],
            "recall_draw": recall[1],
            "recall_away": recall[2],
            "f1_score": f1,
            "log_loss": logloss,
            "brier_score": avg_brier
        }

    def save_backtest_result(self, metrics: Dict[str, Any]) -> BacktestResult:
        """Guarda los resultados del backtest en la BD."""
        result = BacktestResult(
            model_name=metrics["model_name"],
            season=metrics["season"],
            matches_tested=metrics["matches_tested"],
            accuracy=metrics["accuracy"],
            precision_home=metrics["precision_home"],
            precision_draw=metrics["precision_draw"],
            precision_away=metrics["precision_away"],
            recall_home=metrics["recall_home"],
            recall_draw=metrics["recall_draw"],
            recall_away=metrics["recall_away"],
            f1_score=metrics["f1_score"],
            log_loss=metrics["log_loss"],
            brier_score=metrics["brier_score"],
            created_at=datetime.utcnow()
        )

        self.session.add(result)
        self.session.commit()
        logger.info(f"Resultado de backtest guardado para {metrics['model_name']}")
        return result

    def get_historical_results(self) -> List[Dict[str, Any]]:
        """Obtiene resultados históricos de backtests para dashboard."""
        results = self.session.query(BacktestResult).order_by(
            BacktestResult.created_at.desc()
        ).all()
        return [
            {
                "model_name": r.model_name,
                "season": r.season,
                "matches_tested": r.matches_tested,
                "accuracy": r.accuracy,
                "f1_score": r.f1_score,
                "brier_score": r.brier_score,
                "created_at": r.created_at
            }
            for r in results
        ]


if __name__ == "__main__":
    tester = FootballBacktester()

    # Ejemplo: probar todos los modelos
    SEASONS = ["2022-23", "2023-24"]

    for season in SEASONS:
        print("\n" + "="*60)
        print(f"Backtesting temporada {season}")
        print("="*60)

        for model_name in ["poisson", "dixon_coles", "hybrid"]:
            try:
                metrics = tester.run_backtest(model_name, season)
                if metrics:
                    print(f"\n{model_name.upper()}:")
                    print(f"  Accuracy: {metrics['accuracy']:.2%}")
                    print(f"  F1: {metrics['f1_score']:.3f}")
                    print(f"  Brier: {metrics['brier_score']:.4f}")
                    tester.save_backtest_result(metrics)
            except Exception as e:
                logger.error(f"Error en backtest {model_name} ({season}): {e}")
