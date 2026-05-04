import pytest
import numpy as np
from predictor.poisson_model import PoissonModel
from predictor.dixon_coles import DixonColesModel

@pytest.fixture
def mock_teams():
    return {
        "home": {"name": "Team A", "attack": 1.5, "defense": 0.8},
        "away": {"name": "Team B", "attack": 1.2, "defense": 1.1}
    }

def test_poisson_lambdas(mock_teams):
    model = PoissonModel(avg_goals=1.3, home_advantage=1.1)
    lh, la = model.expected_goals(mock_teams["home"], mock_teams["away"])
    assert lh > 0
    assert la > 0
    assert isinstance(lh, float)

def test_dixon_coles_matrix(mock_teams):
    model = DixonColesModel(avg_goals=1.3, home_advantage=1.1)
    matrix = model.score_matrix(mock_teams["home"], mock_teams["away"])
    assert np.isclose(matrix.sum(), 1.0)
    assert matrix.shape == (9, 9) # MAX_GOALS=8 -> 9x9

def test_match_probabilities(mock_teams):
    model = DixonColesModel()
    probs = model.match_probabilities(mock_teams["home"], mock_teams["away"])
    assert "home_win" in probs
    assert "draw" in probs
    assert "away_win" in probs
    assert np.isclose(probs["home_win"] + probs["draw"] + probs["away_win"], 1.0)
