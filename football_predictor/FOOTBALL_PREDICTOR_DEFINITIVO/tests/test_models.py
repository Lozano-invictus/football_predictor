"""
tests/test_models.py
Suite de pruebas para modelos predictivos y utilidades core.
Cubre: PoissonModel, DixonColesModel, HybridModel, DataValidator.
"""
import pytest
import numpy as np
from predictor.poisson_model import PoissonModel
from predictor.dixon_coles import DixonColesModel
from predictor.hybrid_model import HybridModel
from utils import DataValidator


# ------------------------------------------------------------------ #
# FIXTURES
# ------------------------------------------------------------------ #

@pytest.fixture
def mock_teams():
    return {
        "home": {"id": 1, "name": "Team A", "attack": 1.5, "defense": 0.8, "elo": 1600},
        "away": {"id": 2, "name": "Team B", "attack": 1.2, "defense": 1.1, "elo": 1450},
    }

@pytest.fixture
def weak_home():
    """Equipo local muy débil vs visitante fuerte — away_win debería dominar."""
    return {
        "home": {"id": 3, "name": "Weak FC",   "attack": 0.6, "defense": 2.0, "elo": 1200},
        "away": {"id": 4, "name": "Strong CF",  "attack": 2.5, "defense": 0.5, "elo": 1800},
    }


# ------------------------------------------------------------------ #
# POISSON MODEL
# ------------------------------------------------------------------ #

def test_poisson_lambdas(mock_teams):
    model = PoissonModel(avg_goals=1.3, home_advantage=1.1)
    lh, la = model.expected_goals(mock_teams["home"], mock_teams["away"])
    assert lh > 0
    assert la > 0
    assert isinstance(lh, float)

def test_poisson_match_probabilities_sum(mock_teams):
    model = PoissonModel()
    res = model.match_probabilities(mock_teams["home"], mock_teams["away"])
    total = res["home_win"] + res["draw"] + res["away_win"]
    assert np.isclose(total, 1.0, atol=1e-6), f"Probabilidades no suman 1: {total}"

def test_poisson_standard_keys(mock_teams):
    model = PoissonModel()
    res = model.match_probabilities(mock_teams["home"], mock_teams["away"])
    required_keys = {"home_win", "draw", "away_win", "prob_home", "prob_draw",
                     "prob_away", "expected_home", "expected_away", "score_matrix",
                     "top_scores", "model_type"}
    assert required_keys.issubset(res.keys()), f"Faltan claves: {required_keys - res.keys()}"

def test_poisson_top_scores_structure(mock_teams):
    model = PoissonModel()
    res = model.match_probabilities(mock_teams["home"], mock_teams["away"])
    assert len(res["top_scores"]) > 0
    for score in res["top_scores"]:
        assert "home_goals" in score
        assert "away_goals" in score
        assert "probability" in score
        assert 0.0 <= score["probability"] <= 1.0

def test_poisson_home_advantage(mock_teams):
    """Local fuerte debería tener mayor probabilidad de ganar."""
    model = PoissonModel()
    res = model.match_probabilities(mock_teams["home"], mock_teams["away"])
    assert res["home_win"] > res["away_win"]

def test_poisson_simulate_group(mock_teams):
    model = PoissonModel()
    teams = [
        {"name": "A", "attack": 1.5, "defense": 0.8},
        {"name": "B", "attack": 1.2, "defense": 1.1},
        {"name": "C", "attack": 1.0, "defense": 1.0},
        {"name": "D", "attack": 0.9, "defense": 1.3},
    ]
    df = model.simulate_group(teams)
    assert len(df) == 4
    assert "Pts" in df.columns
    assert "GF" in df.columns


# ------------------------------------------------------------------ #
# DIXON-COLES MODEL
# ------------------------------------------------------------------ #

def test_dixon_coles_matrix(mock_teams):
    model = DixonColesModel(avg_goals=1.3, home_advantage=1.1)
    matrix = model.score_matrix(mock_teams["home"], mock_teams["away"])
    assert np.isclose(matrix.sum(), 1.0)
    assert matrix.shape == (10, 10)  # MAX_GOALS=9 -> rango 0..9 -> 10x10

def test_dixon_coles_match_probabilities(mock_teams):
    model = DixonColesModel()
    probs = model.match_probabilities(mock_teams["home"], mock_teams["away"])
    assert "home_win" in probs
    assert "draw" in probs
    assert "away_win" in probs
    assert np.isclose(probs["home_win"] + probs["draw"] + probs["away_win"], 1.0, atol=1e-6)

def test_dixon_coles_standard_keys(mock_teams):
    model = DixonColesModel()
    res = model.match_probabilities(mock_teams["home"], mock_teams["away"])
    required_keys = {"home_win", "draw", "away_win", "prob_home", "prob_draw",
                     "prob_away", "expected_home", "expected_away", "score_matrix",
                     "top_scores", "model_type"}
    assert required_keys.issubset(res.keys())

def test_dixon_coles_top_scores_structure(mock_teams):
    model = DixonColesModel()
    res = model.match_probabilities(mock_teams["home"], mock_teams["away"])
    for score in res["top_scores"]:
        assert "home_goals" in score
        assert "away_goals" in score
        assert "probability" in score

def test_dixon_coles_tau_correction_range(mock_teams):
    """Verifica que la corrección tau genera probabilidades válidas (sin negativos)."""
    model = DixonColesModel()
    matrix = model.score_matrix(mock_teams["home"], mock_teams["away"])
    assert (matrix >= 0).all(), "Hay probabilidades negativas en la matriz"


# ------------------------------------------------------------------ #
# HYBRID MODEL
# ------------------------------------------------------------------ #

def test_hybrid_model_import():
    """Verifica que HybridModel se puede importar sin circular import."""
    model = HybridModel()
    assert model is not None

def test_hybrid_predict_hybrid_keys(mock_teams):
    model = HybridModel()
    res = model.predict_hybrid(mock_teams["home"], mock_teams["away"], season="2025-2026")
    required_keys = {"home_win", "draw", "away_win", "prob_home", "prob_draw",
                     "prob_away", "expected_home", "expected_away", "score_matrix",
                     "top_scores", "hybrid_strength_home", "hybrid_strength_away", "model_type"}
    assert required_keys.issubset(res.keys()), f"Faltan claves: {required_keys - res.keys()}"

def test_hybrid_probabilities_sum(mock_teams):
    model = HybridModel()
    res = model.predict_hybrid(mock_teams["home"], mock_teams["away"], season="2025-2026")
    total = res["home_win"] + res["draw"] + res["away_win"]
    assert np.isclose(total, 1.0, atol=1e-5), f"Probabilidades no suman 1: {total}"

def test_hybrid_top_scores_structure(mock_teams):
    model = HybridModel()
    res = model.predict_hybrid(mock_teams["home"], mock_teams["away"], season="2025-2026")
    assert len(res["top_scores"]) > 0
    for score in res["top_scores"]:
        assert "home_goals" in score
        assert "away_goals" in score
        assert "probability" in score
        assert "score" in score  # compatibilidad con UI

def test_hybrid_predict_match_interface(mock_teams):
    """predict_match debe cumplir la misma interfaz que los otros modelos."""
    model = HybridModel()
    res = model.predict_match(mock_teams["home"], mock_teams["away"], season="2025-2026")
    required_keys = {"home_win", "draw", "away_win", "expected_home",
                     "expected_away", "top_scores", "model_type"}
    assert required_keys.issubset(res.keys())


# ------------------------------------------------------------------ #
# DATA VALIDATOR
# ------------------------------------------------------------------ #

def test_validator_valid_team():
    team = {"name": "Real Madrid", "country": "ESP", "league": "UCL",
            "attack": 1.8, "defense": 0.9}
    assert DataValidator.validate_team(team) is True

def test_validator_missing_field():
    team = {"name": "Test FC", "country": "ESP", "attack": 1.5}
    assert DataValidator.validate_team(team) is False

def test_validator_attack_out_of_range():
    team = {"name": "Test FC", "country": "ESP", "league": "UCL",
            "attack": 10.0, "defense": 1.0}
    assert DataValidator.validate_team(team) is False

def test_validator_defense_out_of_range():
    team = {"name": "Test FC", "country": "ESP", "league": "UCL",
            "attack": 1.5, "defense": 5.0}
    assert DataValidator.validate_team(team) is False

def test_validator_normalize_team_name():
    assert DataValidator.normalize_team_name("R. Madrid") == "Real Madrid"
    assert DataValidator.normalize_team_name("Man. City") == "Manchester City"
    assert DataValidator.normalize_team_name("B. Leverkusen") == "Bayer Leverkusen"
