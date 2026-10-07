-- Raw and parsed source rows for a traceable, repeatable SQLite ETL.
-- Keep one staging record per source data-record ordinal, including rejects.
CREATE TABLE IF NOT EXISTS stg_movie (
    source_record_ordinal INTEGER PRIMARY KEY,
    movie_id              INTEGER,
    title                 TEXT,
    genres_raw            TEXT,
    reject_reason         TEXT
);
CREATE INDEX IF NOT EXISTS ix_stg_movie_id ON stg_movie(movie_id);

CREATE TABLE IF NOT EXISTS stg_link (
    source_record_ordinal INTEGER PRIMARY KEY,
    movie_id              INTEGER,
    imdb_id_raw           TEXT,
    tmdb_id_raw           TEXT,
    reject_reason         TEXT
);
CREATE INDEX IF NOT EXISTS ix_stg_link_movie ON stg_link(movie_id);

CREATE TABLE IF NOT EXISTS stg_rating (
    source_record_ordinal INTEGER PRIMARY KEY,
    raw_user_id           TEXT,
    raw_movie_id          TEXT,
    raw_rating            TEXT,
    raw_timestamp         TEXT,
    user_id               INTEGER,
    movie_id              INTEGER,
    rating                REAL,
    timestamp             INTEGER,
    reject_reason         TEXT
);

CREATE TABLE IF NOT EXISTS stg_user_tag (
    source_record_ordinal INTEGER PRIMARY KEY,
    raw_user_id           TEXT,
    raw_movie_id          TEXT,
    tag_text              TEXT,
    raw_timestamp         TEXT,
    user_id               INTEGER,
    movie_id              INTEGER,
    timestamp             INTEGER,
    tag_key_norm          TEXT,
    reject_reason         TEXT
);

CREATE TABLE IF NOT EXISTS stg_genome_tag (
    source_record_ordinal INTEGER PRIMARY KEY,
    raw_tag_id            TEXT,
    tag_id                INTEGER,
    tag_text              TEXT,
    reject_reason         TEXT
);

CREATE TABLE IF NOT EXISTS stg_genome_score (
    source_record_ordinal INTEGER PRIMARY KEY,
    raw_movie_id          TEXT,
    raw_tag_id            TEXT,
    raw_relevance         TEXT,
    movie_id              INTEGER,
    tag_id                INTEGER,
    relevance             REAL,
    reject_reason         TEXT
);

CREATE TABLE IF NOT EXISTS stg_wikidata_movie (
    movie_id          INTEGER PRIMARY KEY,
    imdb_id           TEXT NOT NULL,
    match_status      TEXT NOT NULL CHECK (match_status IN ('matched', 'unmatched', 'ambiguous')),
    wikidata_qid      TEXT,
    candidate_qids_json TEXT,
    metadata_json     TEXT NOT NULL,
    retrieved_on      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_stg_wikidata_status
    ON stg_wikidata_movie(match_status);
