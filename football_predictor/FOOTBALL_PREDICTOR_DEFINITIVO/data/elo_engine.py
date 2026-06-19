
"""
data/elo_engine.py
MOTOR ELO DINÁMICO PROFESIONAL
Calcula y actualiza ratings Elo para equipos de forma automática.
"""

import math
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from .database import (
    get_session,
    Team,
    Match,
    TeamEloHistory
)


class EloEngine:
    """Motor de cálculo de Elo profesional."""

    # K factor configurable por tipo de partido
    K_FACTORS = {
        'final': 40,
        'semifinal': 35,
        'quarterfinal': 30,
        'round_of_16': 25,
        'group': 20,
        'default': 20
    }

    def __init__(self, default_k: int = 20):
        self.default_k = default_k

    def calculate_expected_score(self, rating_team: float, rating_opponent: float) -> float:
        """
        Calcula la puntuación esperada de un equipo contra otro.
        Formula: E = 1 / (1 + 10^((R_opponent - R_team)/400))
        """
        exponent = (rating_opponent - rating_team) / 400.0
        return 1.0 / (1.0 + math.pow(10, exponent))

    def calculate_elo_change(self, rating_team: float, rating_opponent: float,
                          actual_score: float, k_factor: int) -> Tuple[float, float, float]:
        """
        Calcula el cambio de Elo para ambos equipos.
        actual_score: 1 = victoria, 0.5 = empate, 0 = derrota
        Returns: (new_team_elo, new_opponent_elo, elo_change_for_team)
        """
        expected_team = self.calculate_expected_score(rating_team, rating_opponent)
        expected_opponent = 1.0 - expected_team

        elo_change = k_factor * (actual_score - expected_team)
        opponent_elo_change = -elo_change

        new_team_elo = rating_team + elo_change
        new_opponent_elo = rating_opponent + opponent_elo_change

        return new_team_elo, new_opponent_elo, elo_change

    def determine_k_factor(self, stage: Optional[str]) -> int:
        """Determina el factor K basado en la fase del partido."""
        if not stage:
            return self.default_k

        stage_lower = stage.lower()
        if 'final' in stage_lower and 'semi' not in stage_lower:
            return self.K_FACTORS['final']
        elif 'semi' in stage_lower:
            return self.K_FACTORS['semifinal']
        elif 'quarter' in stage_lower or 'cuartos' in stage_lower:
            return self.K_FACTORS['quarterfinal']
        elif 'octavos' in stage_lower or 'round of 16' in stage_lower:
            return self.K_FACTORS['round_of_16']
        elif 'group' in stage_lower or 'grupo' in stage_lower:
            return self.K_FACTORS['group']
        else:
            return self.default_k

    def process_match_elo(self, match: Match, commit: bool = True,
                        session: Optional[Session] = None) -> Dict:
        """
        Procesa un partido y actualiza el Elo de ambos equipos.
        """
        if session is None:
            session = get_session()

        try:
            # Obtener equipos
            home_team = session.query(Team).filter(Team.id == match.home_team_id).first()
            away_team = session.query(Team).filter(Team.id == match.away_team_id).first()

            if not home_team or not away_team:
                return {"status": "error", "message": "Equipos no encontrados"}

            # Obtener ratings actuales
            old_home_elo = home_team.elo
            old_away_elo = away_team.elo

            # Determinar resultado real
            if match.home_score is None or match.away_score is None:
                return {"status": "error", "message": "Resultado del partido no disponible"}

            if match.home_score > match.away_score:
                home_actual_score = 1.0
                away_actual_score = 0.0
            elif match.home_score < match.away_score:
                home_actual_score = 0.0
                away_actual_score = 1.0
            else:
                home_actual_score = 0.5
                away_actual_score = 0.5

            # Calcular K factor
            k_factor = self.determine_k_factor(match.stage)

            # Calcular nuevos ratings
            new_home_elo, new_away_elo, home_change = self.calculate_elo_change(
                old_home_elo, old_away_elo, home_actual_score, k_factor
            )
            away_change = -home_change

            # Actualizar ratings en tabla Team
            home_team.elo = new_home_elo
            away_team.elo = new_away_elo

            # Guardar historial
            home_history = TeamEloHistory(
                team_id=home_team.id,
                match_id=match.id,
                old_elo=old_home_elo,
                new_elo=new_home_elo,
                elo_change=home_change,
                competition="Champions League",
                season=match.season
            )

            away_history = TeamEloHistory(
                team_id=away_team.id,
                match_id=match.id,
                old_elo=old_away_elo,
                new_elo=new_away_elo,
                elo_change=away_change,
                competition="Champions League",
                season=match.season
            )

            session.add(home_history)
            session.add(away_history)

            if commit:
                session.commit()

            return {
                "status": "success",
                "home_team": home_team.name,
                "away_team": away_team.name,
                "old_home_elo": old_home_elo,
                "new_home_elo": new_home_elo,
                "home_change": home_change,
                "old_away_elo": old_away_elo,
                "new_away_elo": new_away_elo,
                "away_change": away_change,
                "k_factor": k_factor,
                "stage": match.stage
            }

        except Exception as e:
            if commit:
                session.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            if session is not None:
                session.close()

    def rebuild_all_elo_history(self, start_season: str = "2022-23",
                              competition: str = "Champions League") -> Dict:
        """
        Reconstruye todo el historial de Elo desde cero.
        Útil para inicializar el sistema.
        """
        session = get_session()
        processed_matches = 0
        errors = []

        try:
            # Resetear todos los equipos a Elo inicial
            teams = session.query(Team).all()
            for team in teams:
                team.elo = 1500.0

            # Borrar historial existente
            session.query(TeamEloHistory).delete()

            # Obtener partidos ordenados cronológicamente
            matches = session.query(Match).filter(
                Match.season >= start_season,
                Match.status == "FINISHED"
            ).order_by(Match.date).all()

            for match in matches:
                result = self.process_match_elo(match, commit=False, session=session)
                if result["status"] == "success":
                    processed_matches += 1
                else:
                    errors.append(result)

            # Commit final
            session.commit()

            return {
                "status": "success",
                "processed_matches": processed_matches,
                "errors": len(errors),
                "error_details": errors
            }

        except Exception as e:
            session.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    def get_current_elo(self, team_id: int) -> Optional[float]:
        """Obtiene el rating Elo actual de un equipo."""
        session = get_session()
        team = session.query(Team).filter(Team.id == team_id).first()
        session.close()
        return team.elo if team else None

    def get_team_elo_history(self, team_id: int, limit: int = 100) -> List[Dict]:
        """Obtiene el historial completo de Elo para un equipo."""
        session = get_session()
        history = session.query(TeamEloHistory).filter(
            TeamEloHistory.team_id == team_id
        ).order_by(TeamEloHistory.created_at.desc()).limit(limit).all()

        result = []
        for record in history:
            result.append({
                "id": record.id,
                "match_id": record.match_id,
                "old_elo": record.old_elo,
                "new_elo": record.new_elo,
                "elo_change": record.elo_change,
                "competition": record.competition,
                "season": record.season,
                "created_at": record.created_at.isoformat()
            })
        session.close()
        return result

    def get_top_teams(self, limit: int = 10, session: Optional[Session] = None) -> List[Dict]:
        """Obtiene los equipos con mejor rating Elo."""
        if session is None:
            session = get_session()

        try:
            teams = session.query(Team).order_by(Team.elo.desc()).limit(limit).all()
            result = []
            for team in teams:
                result.append({
                    "id": team.id,
                    "name": team.name,
                    "country": team.country,
                    "elo": team.elo,
                    "logo_url": team.logo_url
                })
            return result
        finally:
            if session is not None:
                session.close()
