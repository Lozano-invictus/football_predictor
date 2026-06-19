"""
data/database.py
ESQUEMA RELACIONAL UNIFICADO — UEFA Champions League (2022-2026)
Reconcilia el ORM SQLAlchemy con el esquema real de football_predictor.db
y con los campos que consultan las páginas de la aplicación.
"""

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    ForeignKey, JSON, UniqueConstraint, Boolean, Index, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import config

Base = declarative_base()


# ================================================================ #
# EQUIPOS
# ================================================================ #

class Team(Base):
    __tablename__ = 'teams'

    id           = Column(Integer, primary_key=True)
    name         = Column(String, unique=True, nullable=False, index=True)
    short_name   = Column(String(50), index=True)
    country      = Column(String(100))
    league       = Column(String(100))
    logo_url     = Column(String(500))
    stadium      = Column(String(200))
    ucl_titles   = Column(Integer, default=0)

    # Columnas que existen en la BD real (añadidas para unificación)
    attack       = Column(Float, default=1.0)
    defense      = Column(Float, default=1.0)
    elo          = Column(Float, default=1500.0)
    rank         = Column(Integer, default=999)
    last_updated = Column(String(20))

    # Relaciones
    stats       = relationship("TeamSeasonStats", back_populates="team",
                               cascade="all, delete-orphan")
    players     = relationship("PlayerSeasonStats", back_populates="team",
                               cascade="all, delete-orphan")
    transfers_in  = relationship("Transfer", foreign_keys="Transfer.to_team_id")
    transfers_out = relationship("Transfer", foreign_keys="Transfer.from_team_id")
    coaches     = relationship("Coach", back_populates="team")


# ================================================================ #
# ENTRENADORES
# ================================================================ #

class Coach(Base):
    __tablename__ = 'coaches'

    id          = Column(Integer, primary_key=True)
    name        = Column(String, nullable=False, index=True)
    team_id     = Column(Integer, ForeignKey('teams.id'), nullable=False)
    season      = Column(String(9), nullable=False, index=True)
    nationality = Column(String(100))

    team = relationship("Team", back_populates="coaches")


# ================================================================ #
# ESTADÍSTICAS DE EQUIPO POR TEMPORADA
# ================================================================ #

class TeamSeasonStats(Base):
    __tablename__ = 'team_season_stats'

    id      = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False, index=True)
    season  = Column(String(9), nullable=False, index=True)

    attack_score  = Column(Float, default=1.0)
    defense_score = Column(Float, default=1.0)
    elo_rating    = Column(Float, default=1500.0)

    matches_played    = Column(Integer, default=0)
    wins              = Column(Integer, default=0)
    draws             = Column(Integer, default=0)
    losses            = Column(Integer, default=0)
    goals_for         = Column(Integer, default=0)
    goals_against     = Column(Integer, default=0)

    expected_goals         = Column(Float, default=0.0)
    expected_goals_against = Column(Float, default=0.0)
    possession_avg         = Column(Float, default=50.0)
    pass_accuracy          = Column(Float, default=0.0)
    shots_on_target_avg    = Column(Float, default=0.0)
    distance_avg           = Column(Float, default=115.0)

    group_name    = Column(String(2))
    reached_stage = Column(String(50))

    team = relationship("Team", back_populates="stats")

    __table_args__ = (
        UniqueConstraint('team_id', 'season', name='_team_season_uc'),
        Index('idx_team_season', 'team_id', 'season'),
    )


# ================================================================ #
# JUGADORES
# ================================================================ #

class Player(Base):
    __tablename__ = 'players'

    id            = Column(Integer, primary_key=True)
    name          = Column(String, nullable=False, index=True)
    full_name     = Column(String(250))
    nationality   = Column(String(100), index=True)
    date_of_birth = Column(DateTime)
    image_url     = Column(String(500))

    # position_main es el campo ORM canónico;
    # position es alias para compatibilidad con la BD real y migrate_json_to_db.py
    position_main = Column(String(50), index=True)
    position      = Column(String(50))           # columna que existe en la BD real
    is_active     = Column(Boolean, default=True) # columna que existe en la BD real

    # Relaciones
    stats         = relationship("PlayerSeasonStats", back_populates="player",
                                 cascade="all, delete-orphan")
    transfers     = relationship("Transfer", back_populates="player")
    injuries      = relationship("Injury", back_populates="player")
    value_history = relationship("MarketValueHistory", back_populates="player")


# ================================================================ #
# ESTADÍSTICAS DE JUGADOR POR TEMPORADA
# ================================================================ #

class PlayerSeasonStats(Base):
    __tablename__ = 'player_season_stats'

    id        = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False, index=True)
    team_id   = Column(Integer, ForeignKey('teams.id'), nullable=False, index=True)
    season    = Column(String(9), nullable=False, index=True)

    position      = Column(String(50))
    age_at_season = Column(Integer)
    market_value  = Column(Float)

    minutes_played = Column(Integer, default=0)
    # alias: 'minutes' es el nombre en la BD real
    minutes        = Column(Integer, default=0)

    matches_played  = Column(Integer, default=0)
    goals           = Column(Integer, default=0)
    assists         = Column(Integer, default=0)
    shots_total     = Column(Integer, default=0)
    shots_on_target = Column(Integer, default=0)
    pass_accuracy   = Column(Float, default=0.0)
    yellow_cards    = Column(Integer, default=0)
    red_cards       = Column(Integer, default=0)
    clean_sheets    = Column(Integer, default=0)

    # expected_goals es el campo ORM canónico; xG es alias de la BD real
    expected_goals   = Column(Float, default=0.0)
    xG               = Column(Float, default=0.0)   # columna que existe en la BD real
    expected_assists = Column(Float, default=0.0)

    # rating_avg es el campo ORM canónico; rating es alias de la BD real
    rating_avg   = Column(Float, default=0.0)
    rating       = Column(Float, default=0.0)       # columna que existe en la BD real

    is_current_squad = Column(Boolean, default=True)
    last_updated     = Column(String(20))            # columna que existe en la BD real

    player = relationship("Player", back_populates="stats")
    team   = relationship("Team",   back_populates="players")

    __table_args__ = (
        UniqueConstraint('player_id', 'season', name='_player_season_stats_uc'),
        Index('idx_player_team_season', 'player_id', 'team_id', 'season'),
    )


# ================================================================ #
# HISTORIAL DE VALOR DE MERCADO
# ================================================================ #

class MarketValueHistory(Base):
    __tablename__ = 'market_value_history'

    id        = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False, index=True)
    value     = Column(Float, nullable=False)
    date      = Column(DateTime, default=datetime.utcnow, index=True)

    player = relationship("Player", back_populates="value_history")


# ================================================================ #
# TRANSFERENCIAS
# ================================================================ #

class Transfer(Base):
    __tablename__ = 'transfers'

    id        = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False, index=True)

    # FK canónicas (ORM original)
    from_team_id = Column(Integer, ForeignKey('teams.id'), index=True)
    to_team_id   = Column(Integer, ForeignKey('teams.id'), index=True)

    # Texto plano como fallback (existían en la BD real)
    from_team = Column(String(200))
    to_team   = Column(String(200))

    transfer_type = Column(String(50))
    fee           = Column(Float)
    date          = Column(DateTime, default=datetime.utcnow, index=True)
    season        = Column(String(9), index=True)

    player = relationship("Player", back_populates="transfers")


# ================================================================ #
# LESIONES
# ================================================================ #

class Injury(Base):
    __tablename__ = 'injuries'

    id           = Column(Integer, primary_key=True)
    player_id    = Column(Integer, ForeignKey('players.id'), nullable=False, index=True)
    injury_type  = Column(String(200))
    start_date   = Column(DateTime, index=True)
    end_date     = Column(DateTime)
    is_active    = Column(Boolean, default=True, index=True)

    player = relationship("Player", back_populates="injuries")


# ================================================================ #
# PARTIDOS
# ================================================================ #

class Match(Base):
    __tablename__ = 'matches'

    id     = Column(Integer, primary_key=True)
    season = Column(String(9), index=True)
    date   = Column(DateTime, index=True)
    stage  = Column(String(50), index=True)

    home_team_id = Column(Integer, ForeignKey('teams.id'), index=True)
    away_team_id = Column(Integer, ForeignKey('teams.id'), index=True)

    home_score = Column(Integer)
    away_score = Column(Integer)

    home_xg = Column(Float)
    away_xg = Column(Float)

    possession_home = Column(Float)
    possession_away = Column(Float)

    status = Column(String(20), index=True)

    events = relationship("MatchEvent", back_populates="match",
                          cascade="all, delete-orphan")


# ================================================================ #
# EVENTOS DE PARTIDO
# ================================================================ #

class MatchEvent(Base):
    __tablename__ = 'match_events'

    id         = Column(Integer, primary_key=True)
    match_id   = Column(Integer, ForeignKey('matches.id'), nullable=False, index=True)
    player_id  = Column(Integer, ForeignKey('players.id'), index=True)
    team_id    = Column(Integer, ForeignKey('teams.id'), index=True)
    minute     = Column(Integer)
    event_type = Column(String(50), index=True)  # Goal, Card, Substitution, Assist
    detail     = Column(String(200))

    match = relationship("Match", back_populates="events")


# ================================================================ #
# HISTORIAL DE ELO
# ================================================================ #

class TeamEloHistory(Base):
    __tablename__ = 'team_elo_history'

    id         = Column(Integer, primary_key=True)
    team_id    = Column(Integer, ForeignKey('teams.id'), nullable=False, index=True)
    match_id   = Column(Integer, ForeignKey('matches.id'), nullable=True, index=True)
    old_elo    = Column(Float, nullable=False)
    new_elo    = Column(Float, nullable=False)
    elo_change = Column(Float, nullable=False)
    competition = Column(String(50))
    season      = Column(String(9), index=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    team = relationship("Team")


# ================================================================ #
# RESULTADOS DE BACKTESTING
# ================================================================ #

class BacktestResult(Base):
    __tablename__ = 'backtest_results'

    id                = Column(Integer, primary_key=True)
    model_name        = Column(String(50), nullable=False, index=True)
    season            = Column(String(9), nullable=False, index=True)
    matches_tested    = Column(Integer, nullable=False)
    accuracy          = Column(Float)
    precision_home    = Column(Float)
    precision_draw    = Column(Float)
    precision_away    = Column(Float)
    recall_home       = Column(Float)
    recall_draw       = Column(Float)
    recall_away       = Column(Float)
    f1_score          = Column(Float)
    log_loss          = Column(Float)
    brier_score       = Column(Float)
    created_at        = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_backtest_model_season', 'model_name', 'season'),
    )


# ================================================================ #
# PREDICCIONES
# ================================================================ #

class Prediction(Base):
    __tablename__ = 'predictions'

    id           = Column(Integer, primary_key=True)
    home_team_id = Column(Integer, ForeignKey('teams.id'), nullable=False, index=True)
    away_team_id = Column(Integer, ForeignKey('teams.id'), nullable=False, index=True)

    season = Column(String(9), index=True)
    stage  = Column(String(50))

    model_used = Column(String(50), nullable=False)

    prob_home = Column(Float, nullable=False)
    prob_draw = Column(Float, nullable=False)
    prob_away = Column(Float, nullable=False)

    expected_home = Column(Float)
    expected_away = Column(Float)

    top_score_prediction = Column(String(10))

    # Columnas que existen en la BD real
    actual_home_score = Column(Integer)
    actual_away_score = Column(Integer)
    metadata_json     = Column(Text)          # JSON serializado como texto

    timestamp   = Column(DateTime, default=datetime.utcnow, index=True)
    is_accurate = Column(Boolean, default=None)

    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])

    __table_args__ = (
        Index('idx_prediction_teams_season', 'home_team_id', 'away_team_id', 'season'),
    )


# ================================================================ #
# MOTOR Y SESIONES
# ================================================================ #

engine  = create_engine(f"sqlite:///{config.DB_PATH}")
Session = sessionmaker(bind=engine)


def init_db():
    """Crea todas las tablas (si no existen) en la base de datos."""
    Base.metadata.create_all(engine)


def get_session():
    """Devuelve una nueva sesión de SQLAlchemy. Garantiza tablas al arrancar (idempotente)."""
    # FASE A: nunca fallar por BD vacía / sin tablas
    init_db()
    return Session()
