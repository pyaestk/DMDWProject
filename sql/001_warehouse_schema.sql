-- Initial SQLite star-schema foundation for the MovieLens/Wikidata project.
-- Load dimensions before facts. Raw data is never loaded directly into these
-- tables; the repeatable ETL will stage, validate, and transform each source.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS dim_date (
    date_key       INTEGER PRIMARY KEY, -- YYYYMMDD; reserve 0 for unknown
    calendar_date  TEXT NOT NULL UNIQUE,
    calendar_year  INTEGER NOT NULL,
    quarter_number INTEGER NOT NULL CHECK (quarter_number BETWEEN 1 AND 4),
    month_number   INTEGER NOT NULL CHECK (month_number BETWEEN 1 AND 12),
    day_of_month   INTEGER NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
    day_of_week    INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6)
);

CREATE TABLE IF NOT EXISTS dim_time (
    time_key     INTEGER PRIMARY KEY, -- HHMMSS; reserve 0 for unknown
    hour_number  INTEGER NOT NULL CHECK (hour_number BETWEEN 0 AND 23),
    minute_number INTEGER NOT NULL CHECK (minute_number BETWEEN 0 AND 59),
    second_number INTEGER NOT NULL CHECK (second_number BETWEEN 0 AND 59)
);

CREATE TABLE IF NOT EXISTS dim_user (
    user_key INTEGER PRIMARY KEY,
    user_id  INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_movie (
    movie_key          INTEGER PRIMARY KEY,
    movie_id           INTEGER NOT NULL,
    title              TEXT NOT NULL,
    imdb_id            TEXT,
    tmdb_id            INTEGER,
    wikidata_qid       TEXT,
    release_date       TEXT,
    original_language  TEXT,
    runtime_minutes    REAL,
    valid_from         TEXT NOT NULL,
    valid_to           TEXT,
    is_current         INTEGER NOT NULL CHECK (is_current IN (0, 1)),
    attribute_hash     TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_movie_current
    ON dim_movie(movie_id) WHERE is_current = 1;
CREATE INDEX IF NOT EXISTS ix_dim_movie_imdb
    ON dim_movie(imdb_id);

CREATE TABLE IF NOT EXISTS dim_genre (
    genre_key       INTEGER PRIMARY KEY,
    source_name     TEXT NOT NULL,
    source_genre_id TEXT NOT NULL,
    genre_name      TEXT NOT NULL,
    UNIQUE (source_name, source_genre_id)
);

CREATE TABLE IF NOT EXISTS bridge_movie_genre (
    movie_key INTEGER NOT NULL REFERENCES dim_movie(movie_key),
    genre_key INTEGER NOT NULL REFERENCES dim_genre(genre_key),
    PRIMARY KEY (movie_key, genre_key)
);

CREATE TABLE IF NOT EXISTS dim_country (
    country_key  INTEGER PRIMARY KEY,
    wikidata_qid TEXT NOT NULL UNIQUE,
    country_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bridge_movie_country (
    movie_key   INTEGER NOT NULL REFERENCES dim_movie(movie_key),
    country_key INTEGER NOT NULL REFERENCES dim_country(country_key),
    PRIMARY KEY (movie_key, country_key)
);

CREATE TABLE IF NOT EXISTS dim_language (
    language_key  INTEGER PRIMARY KEY,
    wikidata_qid  TEXT NOT NULL UNIQUE,
    language_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bridge_movie_language (
    movie_key    INTEGER NOT NULL REFERENCES dim_movie(movie_key),
    language_key INTEGER NOT NULL REFERENCES dim_language(language_key),
    PRIMARY KEY (movie_key, language_key)
);

CREATE TABLE IF NOT EXISTS dim_person (
    person_key   INTEGER PRIMARY KEY,
    wikidata_qid TEXT NOT NULL UNIQUE,
    person_name  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bridge_movie_director (
    movie_key  INTEGER NOT NULL REFERENCES dim_movie(movie_key),
    person_key INTEGER NOT NULL REFERENCES dim_person(person_key),
    PRIMARY KEY (movie_key, person_key)
);

CREATE TABLE IF NOT EXISTS dim_user_tag (
    user_tag_key INTEGER PRIMARY KEY,
    tag_text     TEXT NOT NULL,
    tag_key_norm TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_genome_tag (
    genome_tag_key INTEGER PRIMARY KEY,
    source_tag_id  INTEGER NOT NULL UNIQUE,
    tag_text       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_run (
    run_id              INTEGER PRIMARY KEY,
    started_at_utc      TEXT NOT NULL,
    completed_at_utc    TEXT,
    code_version        TEXT,
    source_manifest_json TEXT NOT NULL,
    run_status          TEXT NOT NULL CHECK (run_status IN ('running', 'succeeded', 'failed'))
);

CREATE TABLE IF NOT EXISTS etl_table_audit (
    run_id              INTEGER NOT NULL REFERENCES etl_run(run_id),
    table_name          TEXT NOT NULL,
    source_rows         INTEGER NOT NULL,
    accepted_rows       INTEGER NOT NULL,
    rejected_rows       INTEGER NOT NULL,
    duplicate_rows      INTEGER NOT NULL,
    unmatched_rows      INTEGER NOT NULL,
    loaded_rows         INTEGER NOT NULL,
    PRIMARY KEY (run_id, table_name)
);

CREATE TABLE IF NOT EXISTS etl_quality_issue (
    issue_id        INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES etl_run(run_id),
    source_name     TEXT NOT NULL,
    source_record   TEXT NOT NULL,
    issue_type      TEXT NOT NULL,
    issue_detail    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_etl_issue_run
    ON etl_quality_issue(run_id, source_name, issue_type);

CREATE TABLE IF NOT EXISTS fact_rating (
    rating_event_key TEXT PRIMARY KEY, -- e.g. ml20m:ratings.csv:source-row-ordinal
    user_key         INTEGER NOT NULL REFERENCES dim_user(user_key),
    movie_key        INTEGER NOT NULL REFERENCES dim_movie(movie_key),
    date_key         INTEGER NOT NULL REFERENCES dim_date(date_key),
    time_key         INTEGER NOT NULL REFERENCES dim_time(time_key),
    source_user_id   INTEGER NOT NULL,
    source_movie_id  INTEGER NOT NULL,
    rated_at_unix    INTEGER NOT NULL,
    rating           REAL NOT NULL CHECK (rating BETWEEN 0.5 AND 5.0),
    etl_run_id       INTEGER NOT NULL REFERENCES etl_run(run_id)
);
CREATE INDEX IF NOT EXISTS ix_fact_rating_movie_date
    ON fact_rating(movie_key, date_key);
CREATE INDEX IF NOT EXISTS ix_fact_rating_user_date
    ON fact_rating(user_key, date_key);

CREATE TABLE IF NOT EXISTS fact_tag (
    tag_event_key   TEXT PRIMARY KEY, -- e.g. ml20m:tags.csv:source-row-ordinal
    user_key        INTEGER NOT NULL REFERENCES dim_user(user_key),
    movie_key       INTEGER NOT NULL REFERENCES dim_movie(movie_key),
    user_tag_key    INTEGER NOT NULL REFERENCES dim_user_tag(user_tag_key),
    date_key        INTEGER NOT NULL REFERENCES dim_date(date_key),
    time_key        INTEGER NOT NULL REFERENCES dim_time(time_key),
    source_user_id  INTEGER NOT NULL,
    source_movie_id INTEGER NOT NULL,
    tagged_at_unix  INTEGER NOT NULL,
    etl_run_id      INTEGER NOT NULL REFERENCES etl_run(run_id)
);
CREATE INDEX IF NOT EXISTS ix_fact_tag_movie_date
    ON fact_tag(movie_key, date_key);
CREATE INDEX IF NOT EXISTS ix_fact_tag_text_date
    ON fact_tag(user_tag_key, date_key);

CREATE TABLE IF NOT EXISTS fact_genome_score (
    movie_key      INTEGER NOT NULL REFERENCES dim_movie(movie_key),
    genome_tag_key INTEGER NOT NULL REFERENCES dim_genome_tag(genome_tag_key),
    relevance      REAL NOT NULL CHECK (relevance BETWEEN 0.0 AND 1.0),
    etl_run_id     INTEGER NOT NULL REFERENCES etl_run(run_id),
    PRIMARY KEY (movie_key, genome_tag_key)
);
