-- data/migrations/001_unify_schema.sql
-- Migración incremental: añade columnas faltantes sin borrar datos.
-- Ejecutar UNA sola vez: sqlite3 data/football_predictor.db < data/migrations/001_unify_schema.sql

PRAGMA foreign_keys = OFF;

-- ============================================================
-- teams: añadir columnas del ORM que faltan en la BD real
-- ============================================================
ALTER TABLE teams ADD COLUMN short_name TEXT;
ALTER TABLE teams ADD COLUMN logo_url   TEXT;
ALTER TABLE teams ADD COLUMN stadium    TEXT;

-- ============================================================
-- players: añadir columnas del ORM que faltan en la BD real
-- ============================================================
ALTER TABLE players ADD COLUMN full_name     TEXT;
ALTER TABLE players ADD COLUMN nationality   TEXT;
ALTER TABLE players ADD COLUMN date_of_birth TEXT;
ALTER TABLE players ADD COLUMN image_url     TEXT;
ALTER TABLE players ADD COLUMN position_main TEXT;

-- ============================================================
-- player_season_stats: columnas bidireccionales
-- ============================================================
ALTER TABLE player_season_stats ADD COLUMN position        TEXT;
ALTER TABLE player_season_stats ADD COLUMN age_at_season   INTEGER;
ALTER TABLE player_season_stats ADD COLUMN market_value    REAL;
ALTER TABLE player_season_stats ADD COLUMN minutes_played  INTEGER DEFAULT 0;
ALTER TABLE player_season_stats ADD COLUMN shots_total     INTEGER DEFAULT 0;
ALTER TABLE player_season_stats ADD COLUMN shots_on_target INTEGER DEFAULT 0;
ALTER TABLE player_season_stats ADD COLUMN pass_accuracy   REAL    DEFAULT 0.0;
ALTER TABLE player_season_stats ADD COLUMN yellow_cards    INTEGER DEFAULT 0;
ALTER TABLE player_season_stats ADD COLUMN red_cards       INTEGER DEFAULT 0;
ALTER TABLE player_season_stats ADD COLUMN clean_sheets    INTEGER DEFAULT 0;
ALTER TABLE player_season_stats ADD COLUMN expected_goals  REAL    DEFAULT 0.0;
ALTER TABLE player_season_stats ADD COLUMN expected_assists REAL   DEFAULT 0.0;
ALTER TABLE player_season_stats ADD COLUMN rating_avg      REAL    DEFAULT 0.0;
ALTER TABLE player_season_stats ADD COLUMN is_current_squad INTEGER DEFAULT 1;

-- Backfill: copiar valores de las columnas reales a las canónicas
UPDATE player_season_stats SET expected_goals = xG    WHERE expected_goals = 0 AND xG    IS NOT NULL;
UPDATE player_season_stats SET rating_avg     = rating WHERE rating_avg = 0    AND rating IS NOT NULL;
UPDATE player_season_stats SET minutes_played = minutes WHERE minutes_played = 0 AND minutes IS NOT NULL;

-- ============================================================
-- matches: añadir columnas faltantes en la BD real
-- ============================================================
ALTER TABLE matches ADD COLUMN possession_home REAL;
ALTER TABLE matches ADD COLUMN possession_away REAL;

-- ============================================================
-- team_season_stats: añadir columnas faltantes
-- ============================================================
ALTER TABLE team_season_stats ADD COLUMN wins              INTEGER DEFAULT 0;
ALTER TABLE team_season_stats ADD COLUMN draws             INTEGER DEFAULT 0;
ALTER TABLE team_season_stats ADD COLUMN losses            INTEGER DEFAULT 0;
ALTER TABLE team_season_stats ADD COLUMN expected_goals_against REAL DEFAULT 0.0;
ALTER TABLE team_season_stats ADD COLUMN pass_accuracy     REAL    DEFAULT 0.0;
ALTER TABLE team_season_stats ADD COLUMN shots_on_target_avg REAL  DEFAULT 0.0;

-- ============================================================
-- predictions: columnas cruzadas
-- ============================================================
ALTER TABLE predictions ADD COLUMN season               TEXT;
ALTER TABLE predictions ADD COLUMN stage                TEXT;
ALTER TABLE predictions ADD COLUMN top_score_prediction TEXT;
ALTER TABLE predictions ADD COLUMN is_accurate          INTEGER;

-- ============================================================
-- transfers: añadir FK columns (texto ya existe como from_team/to_team)
-- ============================================================
ALTER TABLE transfers ADD COLUMN from_team_id INTEGER REFERENCES teams(id);
ALTER TABLE transfers ADD COLUMN to_team_id   INTEGER REFERENCES teams(id);
ALTER TABLE transfers ADD COLUMN transfer_type TEXT;
ALTER TABLE transfers ADD COLUMN fee          REAL;

-- ============================================================
-- Tablas nuevas que no existen en la BD real
-- ============================================================
CREATE TABLE IF NOT EXISTS coaches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    team_id     INTEGER NOT NULL REFERENCES teams(id),
    season      TEXT    NOT NULL,
    nationality TEXT
);

CREATE TABLE IF NOT EXISTS market_value_history (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    value     REAL    NOT NULL,
    date      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS match_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id   INTEGER NOT NULL REFERENCES matches(id),
    player_id  INTEGER REFERENCES players(id),
    team_id    INTEGER REFERENCES teams(id),
    minute     INTEGER,
    event_type TEXT,
    detail     TEXT
);

PRAGMA foreign_keys = ON;
