"""
data/data_quality.py
Auditoria reproducible de calidad de datos para el proyecto.

La idea es separar "la app arranca" de "los datos son confiables".
Este modulo no corrige datos: reporta hallazgos accionables.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import re

from sqlalchemy import func

import config
from data.database import (
    get_session,
    Team,
    Player,
    PlayerSeasonStats,
    TeamSeasonStats,
    Match,
    Transfer,
)


SEASON_SHORT_RE = re.compile(r"^\d{4}-\d{2}$")
SEASON_LONG_RE = re.compile(r"^\d{4}-\d{4}$")

DEFAULT_STALE_PLAYER_MARKERS = [
    {
        "player": "Karim Benzema",
        "team": "Real Madrid",
        "reason": "Known stale marker: should not appear in Real Madrid current squad data.",
    },
]


@dataclass
class AuditFinding:
    code: str
    severity: str
    message: str
    count: int = 0
    sample: Optional[List[Dict]] = None


class DataQualityAuditor:
    """Ejecuta chequeos de integridad, consistencia y actualidad local."""

    def __init__(self, current_season: Optional[str] = None):
        self.current_season = current_season or config.CURRENT_SEASON

    @staticmethod
    def _rows_to_dicts(rows, keys: List[str], limit: int = 20) -> List[Dict]:
        return [dict(zip(keys, row)) for row in rows[:limit]]

    @staticmethod
    def _normalize_season_label(season: str) -> str:
        if not season:
            return ""
        if SEASON_LONG_RE.match(season):
            return f"{season[:4]}-{season[-2:]}"
        return season

    def run(self) -> Dict:
        session = get_session()
        findings: List[AuditFinding] = []

        try:
            counts = {
                "teams": session.query(Team).count(),
                "players": session.query(Player).count(),
                "team_season_stats": session.query(TeamSeasonStats).count(),
                "player_season_stats": session.query(PlayerSeasonStats).count(),
                "matches": session.query(Match).count(),
                "transfers": session.query(Transfer).count(),
            }

            self._check_empty_core_tables(counts, findings)
            self._check_duplicates(session, findings)
            self._check_orphans(session, findings)
            self._check_season_formats(session, findings)
            self._check_stat_ranges(session, findings)
            self._check_backtesting_readiness(counts, findings)
            self._check_current_season_coverage(session, findings)
            self._check_stale_player_markers(session, findings)

            status = self._status_from_findings(findings)
            return {
                "status": status,
                "current_season": self.current_season,
                "counts": counts,
                "findings": [asdict(f) for f in findings],
            }
        finally:
            session.close()

    def _check_empty_core_tables(self, counts: Dict[str, int], findings: List[AuditFinding]) -> None:
        for table_name in ["teams", "players", "team_season_stats", "player_season_stats"]:
            if counts.get(table_name, 0) == 0:
                findings.append(AuditFinding(
                    code=f"EMPTY_{table_name.upper()}",
                    severity="HIGH",
                    message=f"La tabla {table_name} esta vacia.",
                    count=0,
                ))

    def _check_duplicates(self, session, findings: List[AuditFinding]) -> None:
        duplicate_teams = (
            session.query(Team.name, func.count(Team.id))
            .group_by(Team.name)
            .having(func.count(Team.id) > 1)
            .all()
        )
        if duplicate_teams:
            findings.append(AuditFinding(
                code="DUPLICATE_TEAMS",
                severity="HIGH",
                message="Hay equipos duplicados por nombre.",
                count=len(duplicate_teams),
                sample=self._rows_to_dicts(duplicate_teams, ["name", "count"]),
            ))

        duplicate_players = (
            session.query(Player.name, func.count(Player.id))
            .group_by(Player.name)
            .having(func.count(Player.id) > 1)
            .all()
        )
        if duplicate_players:
            findings.append(AuditFinding(
                code="DUPLICATE_PLAYERS",
                severity="MEDIUM",
                message="Hay jugadores duplicados por nombre.",
                count=len(duplicate_players),
                sample=self._rows_to_dicts(duplicate_players, ["name", "count"]),
            ))

        duplicate_team_stats = (
            session.query(TeamSeasonStats.team_id, TeamSeasonStats.season, func.count(TeamSeasonStats.id))
            .group_by(TeamSeasonStats.team_id, TeamSeasonStats.season)
            .having(func.count(TeamSeasonStats.id) > 1)
            .all()
        )
        if duplicate_team_stats:
            findings.append(AuditFinding(
                code="DUPLICATE_TEAM_SEASONS",
                severity="HIGH",
                message="Hay estadisticas de equipo duplicadas para la misma temporada.",
                count=len(duplicate_team_stats),
                sample=self._rows_to_dicts(duplicate_team_stats, ["team_id", "season", "count"]),
            ))

        duplicate_player_stats = (
            session.query(PlayerSeasonStats.player_id, PlayerSeasonStats.season, func.count(PlayerSeasonStats.id))
            .group_by(PlayerSeasonStats.player_id, PlayerSeasonStats.season)
            .having(func.count(PlayerSeasonStats.id) > 1)
            .all()
        )
        if duplicate_player_stats:
            findings.append(AuditFinding(
                code="DUPLICATE_PLAYER_SEASONS",
                severity="HIGH",
                message="Hay estadisticas de jugador duplicadas para la misma temporada.",
                count=len(duplicate_player_stats),
                sample=self._rows_to_dicts(duplicate_player_stats, ["player_id", "season", "count"]),
            ))

    def _check_orphans(self, session, findings: List[AuditFinding]) -> None:
        orphan_player_team = (
            session.query(PlayerSeasonStats.id, PlayerSeasonStats.player_id, PlayerSeasonStats.team_id, PlayerSeasonStats.season)
            .outerjoin(Team, PlayerSeasonStats.team_id == Team.id)
            .filter(Team.id.is_(None))
            .all()
        )
        if orphan_player_team:
            findings.append(AuditFinding(
                code="ORPHAN_PLAYER_STATS_TEAM",
                severity="HIGH",
                message="Hay estadisticas de jugador apuntando a equipos inexistentes.",
                count=len(orphan_player_team),
                sample=self._rows_to_dicts(orphan_player_team, ["id", "player_id", "team_id", "season"]),
            ))

        orphan_player = (
            session.query(PlayerSeasonStats.id, PlayerSeasonStats.player_id, PlayerSeasonStats.team_id, PlayerSeasonStats.season)
            .outerjoin(Player, PlayerSeasonStats.player_id == Player.id)
            .filter(Player.id.is_(None))
            .all()
        )
        if orphan_player:
            findings.append(AuditFinding(
                code="ORPHAN_PLAYER_STATS_PLAYER",
                severity="HIGH",
                message="Hay estadisticas de jugador apuntando a jugadores inexistentes.",
                count=len(orphan_player),
                sample=self._rows_to_dicts(orphan_player, ["id", "player_id", "team_id", "season"]),
            ))

        orphan_team_stats = (
            session.query(TeamSeasonStats.id, TeamSeasonStats.team_id, TeamSeasonStats.season)
            .outerjoin(Team, TeamSeasonStats.team_id == Team.id)
            .filter(Team.id.is_(None))
            .all()
        )
        if orphan_team_stats:
            findings.append(AuditFinding(
                code="ORPHAN_TEAM_STATS",
                severity="HIGH",
                message="Hay estadisticas de equipo apuntando a equipos inexistentes.",
                count=len(orphan_team_stats),
                sample=self._rows_to_dicts(orphan_team_stats, ["id", "team_id", "season"]),
            ))

    def _check_season_formats(self, session, findings: List[AuditFinding]) -> None:
        seasons = set()
        for row in session.query(TeamSeasonStats.season).distinct().all():
            if row[0]:
                seasons.add(row[0])
        for row in session.query(PlayerSeasonStats.season).distinct().all():
            if row[0]:
                seasons.add(row[0])
        for row in session.query(Match.season).distinct().all():
            if row[0]:
                seasons.add(row[0])

        invalid = [s for s in sorted(seasons) if not (SEASON_SHORT_RE.match(s) or SEASON_LONG_RE.match(s))]
        if invalid:
            findings.append(AuditFinding(
                code="INVALID_SEASON_FORMAT",
                severity="MEDIUM",
                message="Hay temporadas con formato no reconocido.",
                count=len(invalid),
                sample=[{"season": s} for s in invalid[:20]],
            ))

        normalized = {}
        for season in seasons:
            normalized.setdefault(self._normalize_season_label(season), []).append(season)
        mixed = {k: v for k, v in normalized.items() if len(set(v)) > 1}
        if mixed:
            findings.append(AuditFinding(
                code="MIXED_SEASON_FORMATS",
                severity="HIGH",
                message="Hay una misma temporada representada con formatos distintos.",
                count=len(mixed),
                sample=[{"canonical": k, "variants": sorted(v)} for k, v in mixed.items()],
            ))

    def _check_stat_ranges(self, session, findings: List[AuditFinding]) -> None:
        bad_team_strength = (
            session.query(Team.id, Team.name, Team.attack, Team.defense)
            .filter(
                (Team.attack.is_(None)) |
                (Team.defense.is_(None)) |
                (Team.attack < 0) |
                (Team.attack > 5) |
                (Team.defense < 0) |
                (Team.defense > 5)
            )
            .all()
        )
        if bad_team_strength:
            findings.append(AuditFinding(
                code="BAD_TEAM_STRENGTH_RANGE",
                severity="MEDIUM",
                message="Hay equipos con attack/defense nulos o fuera de rango.",
                count=len(bad_team_strength),
                sample=self._rows_to_dicts(bad_team_strength, ["id", "name", "attack", "defense"]),
            ))

        bad_player_stats = (
            session.query(
                PlayerSeasonStats.id,
                PlayerSeasonStats.player_id,
                PlayerSeasonStats.season,
                PlayerSeasonStats.goals,
                PlayerSeasonStats.assists,
                PlayerSeasonStats.minutes_played,
            )
            .filter(
                (PlayerSeasonStats.goals < 0) |
                (PlayerSeasonStats.assists < 0) |
                (PlayerSeasonStats.minutes_played < 0)
            )
            .all()
        )
        if bad_player_stats:
            findings.append(AuditFinding(
                code="BAD_PLAYER_STATS_RANGE",
                severity="MEDIUM",
                message="Hay estadisticas de jugador negativas.",
                count=len(bad_player_stats),
                sample=self._rows_to_dicts(bad_player_stats, ["id", "player_id", "season", "goals", "assists", "minutes_played"]),
            ))

    def _check_backtesting_readiness(self, counts: Dict[str, int], findings: List[AuditFinding]) -> None:
        if counts.get("matches", 0) == 0:
            findings.append(AuditFinding(
                code="NO_MATCHES_FOR_BACKTESTING",
                severity="HIGH",
                message="No hay partidos cargados; el backtesting real no puede ejecutarse.",
                count=0,
            ))

    def _check_current_season_coverage(self, session, findings: List[AuditFinding]) -> None:
        current_variants = {
            self.current_season,
            self._normalize_season_label(self.current_season),
        }
        player_current = (
            session.query(PlayerSeasonStats)
            .filter(PlayerSeasonStats.season.in_(current_variants))
            .count()
        )
        team_current = (
            session.query(TeamSeasonStats)
            .filter(TeamSeasonStats.season.in_(current_variants))
            .count()
        )
        if team_current == 0:
            findings.append(AuditFinding(
                code="NO_CURRENT_TEAM_STATS",
                severity="HIGH",
                message=f"No hay estadisticas de equipos para la temporada actual ({self.current_season}).",
                count=0,
            ))
        if player_current == 0:
            findings.append(AuditFinding(
                code="NO_CURRENT_PLAYER_STATS",
                severity="HIGH",
                message=f"No hay estadisticas de jugadores para la temporada actual ({self.current_season}).",
                count=0,
            ))

    def _check_stale_player_markers(self, session, findings: List[AuditFinding]) -> None:
        current_variants = {
            self.current_season,
            self._normalize_season_label(self.current_season),
        }
        hits = []
        for marker in DEFAULT_STALE_PLAYER_MARKERS:
            rows = (
                session.query(Player.name, Team.name, PlayerSeasonStats.season)
                .join(PlayerSeasonStats, Player.id == PlayerSeasonStats.player_id)
                .join(Team, PlayerSeasonStats.team_id == Team.id)
                .filter(Player.name.ilike(marker["player"]))
                .filter(Team.name.ilike(marker["team"]))
                .filter(PlayerSeasonStats.season.in_(current_variants))
                .all()
            )
            for row in rows:
                hits.append({
                    "player": row[0],
                    "team": row[1],
                    "season": row[2],
                    "reason": marker["reason"],
                })

        if hits:
            findings.append(AuditFinding(
                code="STALE_CURRENT_SQUAD_MARKER",
                severity="HIGH",
                message="Hay senales de plantillas desactualizadas en la temporada actual.",
                count=len(hits),
                sample=hits[:20],
            ))

    @staticmethod
    def _status_from_findings(findings: List[AuditFinding]) -> str:
        severities = {f.severity for f in findings}
        if "HIGH" in severities:
            return "FAIL"
        if "MEDIUM" in severities:
            return "WARN"
        return "OK"


def run_quality_audit(current_season: Optional[str] = None) -> Dict:
    return DataQualityAuditor(current_season=current_season).run()


if __name__ == "__main__":
    import json

    print(json.dumps(run_quality_audit(), indent=2, ensure_ascii=False))
