"""
data/database.py
ESQUEMA RELACIONAL TOTAL - UEFA Champions League (2022-2026)
Optimizado para análisis histórico, transferencias y rendimiento avanzado.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, JSON, UniqueConstraint, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import config

Base = declarative_base()

class Team(Base):
    __tablename__ = 'teams'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    short_name = Column(String(50), index=True)
    country = Column(String(100))
    league = Column(String(100))
    logo_url = Column(String(500))
    stadium = Column(String(200))
    ucl_titles = Column(Integer, default=0)
    
    # Relaciones
    stats = relationship("TeamSeasonStats", back_populates="team", cascade="all, delete-orphan")
    players = relationship("PlayerSeasonStats", back_populates="team", cascade="all, delete-orphan")
    transfers_in = relationship("Transfer", foreign_keys="Transfer.to_team_id")
    transfers_out = relationship("Transfer", foreign_keys="Transfer.from_team_id")
    coaches = relationship("Coach", back_populates="team")

class Coach(Base):
    __tablename__ = 'coaches'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    season = Column(String(9), nullable=False, index=True)
    nationality = Column(String(100))
    
    team = relationship("Team", back_populates="coaches")

class TeamSeasonStats(Base):
    __tablename__ = 'team_season_stats'
    
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False, index=True)
    season = Column(String(9), nullable=False, index=True)
    
    attack_score = Column(Float, default=1.0)
    defense_score = Column(Float, default=1.0)
    elo_rating = Column(Float, default=1500.0)
    
    # Stats UCL avanzadas
    matches_played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    goals_for = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)
    expected_goals = Column(Float, default=0.0)
    expected_goals_against = Column(Float, default=0.0)
    possession_avg = Column(Float, default=50.0)
    pass_accuracy = Column(Float, default=0.0)
    shots_on_target_avg = Column(Float, default=0.0)
    distance_avg = Column(Float, default=115.0)
    
    group_name = Column(String(2)) 
    reached_stage = Column(String(50)) 
    
    team = relationship("Team", back_populates="stats")
    
    __table_args__ = (
        UniqueConstraint('team_id', 'season', name='_team_season_uc'),
        Index('idx_team_season', 'team_id', 'season'),
    )

class Player(Base):
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    full_name = Column(String(250))
    nationality = Column(String(100), index=True)
    date_of_birth = Column(DateTime)
    image_url = Column(String(500))
    position_main = Column(String(50), index=True)
    
    # Relaciones
    stats = relationship("PlayerSeasonStats", back_populates="player", cascade="all, delete-orphan")
    transfers = relationship("Transfer", back_populates="player")
    injuries = relationship("Injury", back_populates="player")
    value_history = relationship("MarketValueHistory", back_populates="player")

class PlayerSeasonStats(Base):
    __tablename__ = 'player_season_stats'
    
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False, index=True)
    season = Column(String(9), nullable=False, index=True)
    
    position = Column(String(50))
    age_at_season = Column(Integer)
    market_value = Column(Float) 
    
    minutes_played = Column(Integer, default=0)
    matches_played = Column(Integer, default=0)
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    shots_total = Column(Integer, default=0)
    shots_on_target = Column(Integer, default=0)
    pass_accuracy = Column(Float, default=0.0)
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)
    clean_sheets = Column(Integer, default=0)
    expected_goals = Column(Float, default=0.0)
    expected_assists = Column(Float, default=0.0)
    rating_avg = Column(Float, default=0.0)
    
    is_current_squad = Column(Boolean, default=True)
    
    player = relationship("Player", back_populates="stats")
    team = relationship("Team", back_populates="players")
    
    __table_args__ = (
        UniqueConstraint('player_id', 'season', name='_player_season_stats_uc'),
        Index('idx_player_team_season', 'player_id', 'team_id', 'season'),
    )

class MarketValueHistory(Base):
    __tablename__ = 'market_value_history'
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False, index=True)
    value = Column(Float, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    
    player = relationship("Player", back_populates="value_history")

class Transfer(Base):
    __tablename__ = 'transfers'
    
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False, index=True)
    from_team_id = Column(Integer, ForeignKey('teams.id'), index=True)
    to_team_id = Column(Integer, ForeignKey('teams.id'), index=True)
    
    transfer_type = Column(String(50)) 
    fee = Column(Float) 
    date = Column(DateTime, default=datetime.utcnow, index=True)
    season = Column(String(9), index=True)
    
    player = relationship("Player", back_populates="transfers")

class Injury(Base):
    __tablename__ = 'injuries'
    
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False, index=True)
    injury_type = Column(String(200))
    start_date = Column(DateTime, index=True)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True, index=True)
    
    player = relationship("Player", back_populates="injuries")

class Match(Base):
    __tablename__ = 'matches'
    
    id = Column(Integer, primary_key=True)
    season = Column(String(9), index=True)
    date = Column(DateTime, index=True)
    stage = Column(String(50), index=True) 
    
    home_team_id = Column(Integer, ForeignKey('teams.id'), index=True)
    away_team_id = Column(Integer, ForeignKey('teams.id'), index=True)
    
    home_score = Column(Integer)
    away_score = Column(Integer)
    
    home_xg = Column(Float)
    away_xg = Column(Float)
    
    possession_home = Column(Float)
    possession_away = Column(Float)
    
    status = Column(String(20), index=True) 
    
    events = relationship("MatchEvent", back_populates="match", cascade="all, delete-orphan")

class MatchEvent(Base):
    __tablename__ = 'match_events'
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey('players.id'), index=True)
    team_id = Column(Integer, ForeignKey('teams.id'), index=True)
    minute = Column(Integer)
    event_type = Column(String(50), index=True) # Goal, Card, Substitution, Assist
    detail = Column(String(200))
    
    match = relationship("Match", back_populates="events")


class Prediction(Base):
    """Tabla para almacenar predicciones de partidos."""
    __tablename__ = 'predictions'
    
    id = Column(Integer, primary_key=True)
    home_team_id = Column(Integer, ForeignKey('teams.id'), nullable=False, index=True)
    away_team_id = Column(Integer, ForeignKey('teams.id'), nullable=False, index=True)
    
    season = Column(String(9), index=True)
    stage = Column(String(50))  # Group, Round of 16, Quarterfinals, etc.
    
    model_used = Column(String(50), nullable=False)  # Poisson, Dixon-Coles, Hybrid
    
    prob_home = Column(Float, nullable=False)
    prob_draw = Column(Float, nullable=False)
    prob_away = Column(Float, nullable=False)
    
    expected_home = Column(Float)
    expected_away = Column(Float)
    
    top_score_prediction = Column(String(10))  # e.g., "2-1"
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    is_accurate = Column(Boolean, default=None)  # True/False after match completes
    
    # Relaciones
    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    
    __table_args__ = (
        Index('idx_prediction_teams_season', 'home_team_id', 'away_team_id', 'season'),
    )


# ================================================================ #
# CONFIGURACIÓN DEL MOTOR Y SESIONES
# ================================================================ #

engine = create_engine(f"sqlite:///{config.DB_PATH}")
Session = sessionmaker(bind=engine)

def init_db():
    """Crea todas las tablas en la base de datos."""
    Base.metadata.create_all(engine)

def get_session():
    """Devuelve una nueva sesión de SQLAlchemy."""
    return Session()
    minute = Column(Integer)
    event_type = Column(String(50), index=True) # Goal, Card, Substitution, Assist
    detail = Column(String(200))
    
    match = relationship("Match", back_populates="events")


# Configuración del motor
engine = create_engine(f"sqlite:///{config.DB_PATH}")
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

def get_session():
    return Session()
