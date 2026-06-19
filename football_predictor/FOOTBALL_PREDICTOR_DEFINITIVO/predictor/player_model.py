"""
predictor/player_model.py
Regresión lineal múltiple para predicción de estadísticas individuales.
Reproduce la metodología del TFG (goleadores, porteros, defensas).
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error
from typing import Dict, List, Tuple, Optional


class PlayerModel:
    """
    Entrena un modelo de regresión lineal para una métrica objetivo
    dadas variables independientes de rendimiento histórico.
    """

    def __init__(self):
        self._models: Dict[str, LinearRegression] = {}

    # ------------------------------------------------------------------ #
    # GOLEADORES
    # ------------------------------------------------------------------ #

    def fit_strikers(self, df: pd.DataFrame) -> Dict:
        """
        Variables independientes: shots_attempted, shots_on_target
        Variable dependiente:     goals
        """
        X = df[["shots_attempted", "shots_on_target"]].values
        y = df["goals"].values
        model = LinearRegression().fit(X, y)
        self._models["strikers"] = model
        return self._model_stats(model, X, y)

    def predict_goals(self, shots_attempted: int,
                      shots_on_target: int) -> float:
        model = self._get_model("strikers")
        pred = model.predict([[shots_attempted, shots_on_target]])
        return max(0.0, round(float(pred[0]), 2))

    def rank_strikers(self, df: pd.DataFrame) -> pd.DataFrame:
        self.fit_strikers(df)
        df = df.copy()
        df["predicted_goals"] = df.apply(
            lambda r: self.predict_goals(r["shots_attempted"],
                                         r["shots_on_target"]), axis=1
        )
        return df.sort_values("predicted_goals", ascending=False).reset_index(drop=True)

    # ------------------------------------------------------------------ #
    # PORTEROS
    # ------------------------------------------------------------------ #

    def fit_goalkeepers(self, df: pd.DataFrame) -> Dict:
        """
        Variables independientes: saves, clean_sheets
        Variable dependiente:     goals_conceded (por partido)
        """
        X = df[["saves", "clean_sheets"]].values
        y = df["goals_conceded"].values
        model = LinearRegression().fit(X, y)
        self._models["goalkeepers"] = model
        return self._model_stats(model, X, y)

    def predict_goals_conceded(self, saves: float,
                                clean_sheets: int) -> float:
        model = self._get_model("goalkeepers")
        pred = model.predict([[saves, clean_sheets]])
        return max(0.0, round(float(pred[0]), 2))

    def rank_goalkeepers(self, df: pd.DataFrame) -> pd.DataFrame:
        self.fit_goalkeepers(df)
        df = df.copy()
        df["predicted_conceded"] = df.apply(
            lambda r: self.predict_goals_conceded(r["saves"],
                                                   r["clean_sheets"]), axis=1
        )
        return df.sort_values("predicted_conceded", ascending=True).reset_index(drop=True)

    # ------------------------------------------------------------------ #
    # DEFENSAS
    # ------------------------------------------------------------------ #

    def fit_defenders(self, df: pd.DataFrame) -> Dict:
        """
        Variables independientes: tackles, tackles_won
        Variable dependiente:     balls_recovered (por partido)
        """
        X = df[["tackles", "tackles_won"]].values
        y = df["balls_recovered"].values
        model = LinearRegression().fit(X, y)
        self._models["defenders"] = model
        return self._model_stats(model, X, y)

    def predict_balls_recovered(self, tackles: float,
                                  tackles_won: float) -> float:
        model = self._get_model("defenders")
        pred = model.predict([[tackles, tackles_won]])
        return max(0.0, round(float(pred[0]), 2))

    def rank_defenders(self, df: pd.DataFrame) -> pd.DataFrame:
        self.fit_defenders(df)
        df = df.copy()
        df["predicted_recovered"] = df.apply(
            lambda r: self.predict_balls_recovered(r["tackles"],
                                                    r["tackles_won"]), axis=1
        )
        return df.sort_values("predicted_recovered", ascending=False).reset_index(drop=True)

    # ------------------------------------------------------------------ #
    # PRIVADOS
    # ------------------------------------------------------------------ #

    def _get_model(self, key: str) -> LinearRegression:
        if key not in self._models:
            raise RuntimeError(
                f"Modelo '{key}' no entrenado. Llama primero a fit_{key}()."
            )
        return self._models[key]

    @staticmethod
    def _model_stats(model: LinearRegression,
                     X: np.ndarray, y: np.ndarray) -> Dict:
        y_pred = model.predict(X)
        return {
            "r2":         round(r2_score(y, y_pred), 4),
            "mae":        round(mean_absolute_error(y, y_pred), 4),
            "coef":       model.coef_.tolist(),
            "intercept":  round(float(model.intercept_), 4),
        }
