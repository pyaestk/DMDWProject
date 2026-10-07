#!/usr/bin/env python3
"""Stage MovieLens and Wikidata, then build the SQLite movie warehouse."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = ROOT / "ml-20m"
DEFAULT_WIKIDATA = ROOT / "outputs/source_audit/wikidata_match_full_catalog_2026-09-28.json"
DEFAULT_DB = ROOT / "data/warehouse/movie_preference.sqlite"
DEFAULT_REPORT_DIR = ROOT / "outputs/etl"
BATCH_SIZE = 50_000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def positive_int(raw: str | None) -> int | None:
    try:
        value = int(raw.strip()) if raw is not None else 0
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def nonnegative_int(raw: str | None) -> int | None:
    try:
        value = int(raw.strip()) if raw is not None else -1
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def normalized_tag(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip().casefold()


def normalized_imdb(raw: str | None) -> str | None:
    value = (raw or "").strip()
    if not value or not value.strip("0"):
        return None
    if not value.isdigit():
        return None
    return "tt" + value.zfill(7)


def parse_runtime(values: list[dict]) -> float | None:
    unique: set[float] = set()
    for item in values:
        try:
            number = float(item["amount"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(number) and number > 0:
            unique.add(number)
    return next(iter(unique)) if len(unique) == 1 else None


def parse_language(values: list[dict]) -> str | None:
    labels = {str(item.get("label", "")).strip() for item in values if item.get("label")}
    return next(iter(labels)) if len(labels) == 1 else None


def canonical_release_date(values: list[dict]) -> str | None:
    dates: set[str] = set()
    for item in values:
        value = str(item.get("time", ""))
        if value.startswith("+"):
            value = value[1:]
        if len(value) >= 10 and value[:4].isdigit() and value[4] == "-":
            dates.add(value[:10])
    return min(dates) if dates else None


def issue(conn: sqlite3.Connection, run_id: int, source: str, record: str, kind: str, detail: str) -> None:
    conn.execute(
        "INSERT INTO etl_quality_issue(run_id, source_name, source_record, issue_type, issue_detail) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, source, record, kind, detail[:1000]),
    )


def insert_csv_stage(
    conn: sqlite3.Connection,
    run_id: int,
    path: Path,
    expected_fields: set[str],
    table: str,
    transform: Callable[[int, dict[str, str]], tuple[tuple, str | None]],
    chunk_size: int,
) -> tuple[int, int, int]:
    count = accepted = rejected = 0
    batch: list[tuple] = []
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        actual = set(reader.fieldnames or [])
        if actual != expected_fields:
            raise RuntimeError(
                f"Unexpected columns in {path.name}: expected {sorted(expected_fields)}, "
                f"found {sorted(actual)}"
            )
        for ordinal, row in enumerate(reader, start=1):
            values, reason = transform(ordinal, row)
            batch.append(values)
            count += 1
            if reason:
                rejected += 1
                issue(conn, run_id, path.name, str(ordinal), "invalid_source_row", reason)
            else:
                accepted += 1
            if len(batch) >= chunk_size:
                conn.executemany(table, batch)
                conn.commit()
                batch.clear()
            if count % 1_000_000 == 0:
                print(f"Staged {path.name}: {count:,} records", flush=True)
    if batch:
        conn.executemany(table, batch)
        conn.commit()
    return count, accepted, rejected


def parse_movie(ordinal: int, row: dict[str, str]) -> tuple[tuple, str | None]:
    movie_id = positive_int(row.get("movieId"))
    title = (row.get("title") or "").strip()
    reason = None if movie_id and title else "movieId must be positive and title must be nonblank"
    return (ordinal, movie_id, title or None, row.get("genres", ""), reason), reason


def parse_link(ordinal: int, row: dict[str, str]) -> tuple[tuple, str | None]:
    movie_id = positive_int(row.get("movieId"))
    reason = None if movie_id else "movieId must be a positive integer"
    return (
        ordinal,
        movie_id,
        row.get("imdbId", ""),
        row.get("tmdbId", ""),
        reason,
    ), reason


def parse_rating(ordinal: int, row: dict[str, str]) -> tuple[tuple, str | None]:
    user_id = positive_int(row.get("userId"))
    movie_id = positive_int(row.get("movieId"))
    timestamp = nonnegative_int(row.get("timestamp"))
    try:
        rating = float(row.get("rating", ""))
    except (TypeError, ValueError):
        rating = None
    reason = None
    if not user_id or not movie_id:
        reason = "userId and movieId must be positive integers"
    elif timestamp is None:
        reason = "timestamp must be a nonnegative Unix-seconds integer"
    elif (
        rating is None
        or not math.isfinite(rating)
        or not 0.5 <= rating <= 5.0
        or abs(rating * 2 - round(rating * 2)) > 1e-9
    ):
        reason = "rating must be a half-star value between 0.5 and 5.0"
    return (
        ordinal,
        row.get("userId", ""),
        row.get("movieId", ""),
        row.get("rating", ""),
        row.get("timestamp", ""),
        user_id,
        movie_id,
        rating,
        timestamp,
        reason,
    ), reason


def parse_user_tag(ordinal: int, row: dict[str, str]) -> tuple[tuple, str | None]:
    user_id = positive_int(row.get("userId"))
    movie_id = positive_int(row.get("movieId"))
    timestamp = nonnegative_int(row.get("timestamp"))
    tag_text = row.get("tag", "")
    reason = None
    if not user_id or not movie_id:
        reason = "userId and movieId must be positive integers"
    elif timestamp is None:
        reason = "timestamp must be a nonnegative Unix-seconds integer"
    elif not tag_text.strip():
        reason = "tag text must be nonblank"
    return (
        ordinal,
        row.get("userId", ""),
        row.get("movieId", ""),
        tag_text,
        row.get("timestamp", ""),
        user_id,
        movie_id,
        timestamp,
        normalized_tag(tag_text),
        reason,
    ), reason


def parse_genome_tag(ordinal: int, row: dict[str, str]) -> tuple[tuple, str | None]:
    tag_id = positive_int(row.get("tagId"))
    tag_text = row.get("tag", "")
    reason = None if tag_id and tag_text.strip() else "tagId must be positive and tag text nonblank"
    return (ordinal, row.get("tagId", ""), tag_id, tag_text, reason), reason


def parse_genome_score(ordinal: int, row: dict[str, str]) -> tuple[tuple, str | None]:
    movie_id = positive_int(row.get("movieId"))
    tag_id = positive_int(row.get("tagId"))
    try:
        relevance = float(row.get("relevance", ""))
    except (TypeError, ValueError):
        relevance = None
    reason = None
    if not movie_id or not tag_id:
        reason = "movieId and tagId must be positive integers"
    elif relevance is None or not math.isfinite(relevance) or not 0.0 <= relevance <= 1.0:
        reason = "relevance must be numeric and between 0.0 and 1.0"
    return (
        ordinal,
        row.get("movieId", ""),
        row.get("tagId", ""),
        row.get("relevance", ""),
        movie_id,
        tag_id,
        relevance,
        reason,
    ), reason


def count_rows(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> int:
    return int(conn.execute(sql, args).fetchone()[0])


def duplicate_excess(conn: sqlite3.Connection, table: str, fields: str) -> int:
    return count_rows(
        conn,
        f"SELECT COALESCE(SUM(n - 1), 0) FROM "
        f"(SELECT COUNT(*) AS n FROM {table} WHERE reject_reason IS NULL "
        f"GROUP BY {fields} HAVING COUNT(*) > 1)",
    )


def save_table_audit(
    conn: sqlite3.Connection,
    run_id: int,
    table: str,
    source_rows: int,
    accepted: int,
    rejected: int,
    duplicates: int,
    unmatched: int,
    loaded: int,
) -> dict:
    record = {
        "table": table,
        "sourceRows": source_rows,
        "acceptedRows": accepted,
        "rejectedRows": rejected,
        "duplicateRows": duplicates,
        "unmatchedRows": unmatched,
        "loadedRows": loaded,
    }
    conn.execute(
        "INSERT OR REPLACE INTO etl_table_audit "
        "(run_id, table_name, source_rows, accepted_rows, rejected_rows, duplicate_rows, unmatched_rows, loaded_rows) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, table, source_rows, accepted, rejected, duplicates, unmatched, loaded),
    )
    return record


def load_wikidata_stage(
    conn: sqlite3.Connection, run_id: int, path: Path
) -> tuple[dict[int, dict], dict]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    summary = obj["summary"]
    if not summary.get("fullCatalog"):
        raise RuntimeError("Wikidata input is not marked as a full-catalog audit")
    matches = obj["matches"]
    if len(matches) != summary.get("selectedTitleCount"):
        raise RuntimeError("Wikidata audit row count does not match its summary")
    rows = []
    records: dict[int, dict] = {}
    exact = unmatched = ambiguous = 0
    for record in matches:
        movie_id = positive_int(record.get("movieId"))
        if movie_id is None:
            raise RuntimeError("Wikidata audit contains an invalid MovieLens movieId")
        records[movie_id] = record
        status = record["matchStatus"]
        exact += status == "matched"
        unmatched += status == "unmatched"
        ambiguous += status == "ambiguous"
        qid = record.get("wikidataQid") if status == "matched" else None
        candidate_ids = record.get("wikidataQid") if status == "ambiguous" else None
        rows.append(
            (
                movie_id,
                record["imdbId"],
                status,
                qid,
                json.dumps(candidate_ids, ensure_ascii=False) if candidate_ids else None,
                json.dumps(record, ensure_ascii=False, separators=(",", ":")),
                summary["retrievedOn"],
            )
        )
    if (exact, unmatched, ambiguous) != (
        summary["matched"], summary["unmatched"], summary["ambiguous"]
    ):
        raise RuntimeError("Wikidata audit status counts do not reconcile")
    conn.executemany(
        "INSERT INTO stg_wikidata_movie "
        "(movie_id, imdb_id, match_status, wikidata_qid, candidate_qids_json, metadata_json, retrieved_on) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    for row in rows:
        status = row[2]
        if status == "unmatched":
            issue(conn, run_id, "Wikidata", str(row[0]), "no_exact_match", "No Wikidata P345 item")
        elif status == "ambiguous":
            issue(
                conn,
                run_id,
                "Wikidata",
                str(row[0]),
                "ambiguous_match",
                f"Candidate QIDs: {row[4]}",
            )
    conn.commit()
    audit = {
        "sourceRows": len(rows),
        "acceptedRows": len(rows),
        "rejectedRows": 0,
        "exactMatches": exact,
        "unmatchedRows": unmatched,
        "ambiguousRows": ambiguous,
        "matchRate": summary["matchRate"],
        "uniqueWikidataQids": summary.get("uniqueWikidataQids"),
        "duplicateQidCount": summary.get("duplicateQidCount"),
        "attributeCoverageAmongMatched": summary.get("attributeCoverageAmongMatched", {}),
        "attributeCoverageRateAmongMatched": summary.get("attributeCoverageRateAmongMatched", {}),
        "retrievedOn": summary["retrievedOn"],
    }
    return records, audit


def unique_metadata_items(record: dict | None, field: str) -> list[tuple[str, str]]:
    if not record or record.get("matchStatus") != "matched":
        return []
    items = record.get(field) or []
    unique: dict[str, str] = {}
    for item in items:
        qid = str(item.get("id", "")).strip()
        label = str(item.get("label", "")).strip()
        if qid:
            unique[qid] = label or qid
    return sorted(unique.items())


def build_movie_attributes(
    movie: sqlite3.Row,
    link: sqlite3.Row | None,
    wikidata: dict | None,
) -> tuple[dict, dict]:
    record = wikidata if wikidata and wikidata.get("matchStatus") == "matched" else None
    movie_genres = sorted(
        {part.strip() for part in (movie["genres_raw"] or "").split("|") if part.strip()}
    )
    if not movie_genres or movie_genres == ["(no genres listed)"]:
        movie_genres = ["Unclassified"]
    external_genres = unique_metadata_items(record, "genres")
    languages = unique_metadata_items(record, "languages")
    countries = unique_metadata_items(record, "countries")
    directors = unique_metadata_items(record, "directors")
    releases = (record or {}).get("releaseDates", [])
    runtime_items = (record or {}).get("runtimes", [])
    imdb_id = normalized_imdb(link["imdb_id_raw"] if link else None)
    if record and record.get("imdbId"):
        imdb_id = record["imdbId"]
    tmdb_id = positive_int(link["tmdb_id_raw"] if link else None)
    attributes = {
        "title": movie["title"],
        "imdbId": imdb_id,
        "tmdbId": tmdb_id,
        "wikidataQid": (record or {}).get("wikidataQid"),
        "releaseDate": canonical_release_date(releases),
        "originalLanguage": parse_language([{"label": label} for _, label in languages]),
        "runtimeMinutes": parse_runtime(runtime_items),
        "movieLensGenres": movie_genres,
        "wikidataGenres": external_genres,
        "languages": languages,
        "countries": countries,
        "directors": directors,
    }
    encoded = json.dumps(attributes, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    attributes["attributeHash"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    relationships = {
        "movieGenres": [("MovieLens", name, name) for name in movie_genres],
        "wikidataGenres": [("Wikidata", qid, label) for qid, label in external_genres],
        "languages": languages,
        "countries": countries,
        "directors": directors,
    }
    return attributes, relationships


def load_movie_dimension(
    conn: sqlite3.Connection,
    run_at: str,
    wikidata_records: dict[int, dict],
) -> tuple[dict[int, int], int]:
    links: dict[int, sqlite3.Row] = {}
    for row in conn.execute(
        "SELECT movie_id, imdb_id_raw, tmdb_id_raw FROM stg_link "
        "WHERE reject_reason IS NULL ORDER BY source_record_ordinal"
    ):
        links.setdefault(int(row[0]), row)
    movie_keys: dict[int, int] = {}
    changed_or_inserted = 0
    movies = conn.execute(
        "SELECT source_record_ordinal, movie_id, title, genres_raw FROM stg_movie "
        "WHERE reject_reason IS NULL ORDER BY source_record_ordinal"
    )
    for movie in movies:
        movie_id = int(movie["movie_id"])
        if movie_id in movie_keys:
            continue
        attributes, relationships = build_movie_attributes(
            movie, links.get(movie_id), wikidata_records.get(movie_id)
        )
        current = conn.execute(
            "SELECT movie_key, attribute_hash FROM dim_movie WHERE movie_id=? AND is_current=1",
            (movie_id,),
        ).fetchone()
        if current and current["attribute_hash"] == attributes["attributeHash"]:
            movie_key = int(current["movie_key"])
        else:
            if current:
                conn.execute(
                    "UPDATE dim_movie SET is_current=0, valid_to=? WHERE movie_key=?",
                    (run_at, current["movie_key"]),
                )
            cursor = conn.execute(
                "INSERT INTO dim_movie "
                "(movie_id, title, imdb_id, tmdb_id, wikidata_qid, release_date, original_language, "
                "runtime_minutes, valid_from, valid_to, is_current, attribute_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 1, ?)",
                (
                    movie_id,
                    attributes["title"],
                    attributes["imdbId"],
                    attributes["tmdbId"],
                    attributes["wikidataQid"],
                    attributes["releaseDate"],
                    attributes["originalLanguage"],
                    attributes["runtimeMinutes"],
                    run_at,
                    attributes["attributeHash"],
                ),
            )
            movie_key = int(cursor.lastrowid)
            changed_or_inserted += 1
        movie_keys[movie_id] = movie_key
        for source_name, source_id, label in relationships["movieGenres"] + relationships["wikidataGenres"]:
            conn.execute(
                "INSERT OR IGNORE INTO dim_genre(source_name, source_genre_id, genre_name) VALUES (?, ?, ?)",
                (source_name, source_id, label),
            )
            genre_key = conn.execute(
                "SELECT genre_key FROM dim_genre WHERE source_name=? AND source_genre_id=?",
                (source_name, source_id),
            ).fetchone()[0]
            conn.execute(
                "INSERT OR IGNORE INTO bridge_movie_genre(movie_key, genre_key) VALUES (?, ?)",
                (movie_key, genre_key),
            )
        for qid, label in relationships["languages"]:
            conn.execute(
                "INSERT OR IGNORE INTO dim_language(wikidata_qid, language_name) VALUES (?, ?)",
                (qid, label),
            )
            language_key = conn.execute(
                "SELECT language_key FROM dim_language WHERE wikidata_qid=?", (qid,)
            ).fetchone()[0]
            conn.execute(
                "INSERT OR IGNORE INTO bridge_movie_language(movie_key, language_key) VALUES (?, ?)",
                (movie_key, language_key),
            )
        for qid, label in relationships["countries"]:
            conn.execute(
                "INSERT OR IGNORE INTO dim_country(wikidata_qid, country_name) VALUES (?, ?)",
                (qid, label),
            )
            country_key = conn.execute(
                "SELECT country_key FROM dim_country WHERE wikidata_qid=?", (qid,)
            ).fetchone()[0]
            conn.execute(
                "INSERT OR IGNORE INTO bridge_movie_country(movie_key, country_key) VALUES (?, ?)",
                (movie_key, country_key),
            )
        for qid, label in relationships["directors"]:
            conn.execute(
                "INSERT OR IGNORE INTO dim_person(wikidata_qid, person_name) VALUES (?, ?)",
                (qid, label),
            )
            person_key = conn.execute(
                "SELECT person_key FROM dim_person WHERE wikidata_qid=?", (qid,)
            ).fetchone()[0]
            conn.execute(
                "INSERT OR IGNORE INTO bridge_movie_director(movie_key, person_key) VALUES (?, ?)",
                (movie_key, person_key),
            )
        if movie_id % 5_000 == 0:
            conn.commit()
            print(f"Built movie dimension through movieId {movie_id}", flush=True)
    conn.commit()
    return movie_keys, changed_or_inserted


def prepare_date_and_time_dimensions(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT OR IGNORE INTO dim_date
        (date_key, calendar_date, calendar_year, quarter_number, month_number, day_of_month, day_of_week)
        SELECT CAST(strftime('%Y%m%d', timestamp, 'unixepoch') AS INTEGER),
               date(timestamp, 'unixepoch'),
               CAST(strftime('%Y', timestamp, 'unixepoch') AS INTEGER),
               (CAST(strftime('%m', timestamp, 'unixepoch') AS INTEGER) + 2) / 3,
               CAST(strftime('%m', timestamp, 'unixepoch') AS INTEGER),
               CAST(strftime('%d', timestamp, 'unixepoch') AS INTEGER),
               CAST(strftime('%w', timestamp, 'unixepoch') AS INTEGER)
        FROM stg_rating WHERE reject_reason IS NULL
        UNION
        SELECT CAST(strftime('%Y%m%d', timestamp, 'unixepoch') AS INTEGER),
               date(timestamp, 'unixepoch'),
               CAST(strftime('%Y', timestamp, 'unixepoch') AS INTEGER),
               (CAST(strftime('%m', timestamp, 'unixepoch') AS INTEGER) + 2) / 3,
               CAST(strftime('%m', timestamp, 'unixepoch') AS INTEGER),
               CAST(strftime('%d', timestamp, 'unixepoch') AS INTEGER),
               CAST(strftime('%w', timestamp, 'unixepoch') AS INTEGER)
        FROM stg_user_tag WHERE reject_reason IS NULL;

        INSERT OR IGNORE INTO dim_time(time_key, hour_number, minute_number, second_number)
        SELECT CAST(strftime('%H%M%S', timestamp, 'unixepoch') AS INTEGER),
               CAST(strftime('%H', timestamp, 'unixepoch') AS INTEGER),
               CAST(strftime('%M', timestamp, 'unixepoch') AS INTEGER),
               CAST(strftime('%S', timestamp, 'unixepoch') AS INTEGER)
        FROM stg_rating WHERE reject_reason IS NULL
        UNION
        SELECT CAST(strftime('%H%M%S', timestamp, 'unixepoch') AS INTEGER),
               CAST(strftime('%H', timestamp, 'unixepoch') AS INTEGER),
               CAST(strftime('%M', timestamp, 'unixepoch') AS INTEGER),
               CAST(strftime('%S', timestamp, 'unixepoch') AS INTEGER)
        FROM stg_user_tag WHERE reject_reason IS NULL;
        """
    )
    conn.commit()


def build_facts(conn: sqlite3.Connection, run_id: int) -> dict[str, int]:
    conn.execute("DROP INDEX IF EXISTS ix_fact_rating_movie_date")
    conn.execute("DROP INDEX IF EXISTS ix_fact_rating_user_date")
    conn.execute("DROP INDEX IF EXISTS ix_fact_tag_movie_date")
    conn.execute("DROP INDEX IF EXISTS ix_fact_tag_text_date")
    conn.commit()

    before = conn.total_changes
    conn.execute(
        """
        INSERT OR IGNORE INTO fact_rating
        (rating_event_key, user_key, movie_key, date_key, time_key,
         source_user_id, source_movie_id, rated_at_unix, rating, etl_run_id)
        SELECT 'ml20m:ratings.csv:' || s.source_record_ordinal,
               u.user_key, m.movie_key,
               CAST(strftime('%Y%m%d', s.timestamp, 'unixepoch') AS INTEGER),
               CAST(strftime('%H%M%S', s.timestamp, 'unixepoch') AS INTEGER),
               s.user_id, s.movie_id, s.timestamp, s.rating, ?
        FROM stg_rating s
        JOIN dim_user u ON u.user_id=s.user_id
        JOIN dim_movie m ON m.movie_id=s.movie_id AND m.is_current=1
        WHERE s.reject_reason IS NULL
          AND EXISTS (SELECT 1 FROM dim_date d WHERE d.date_key=CAST(strftime('%Y%m%d', s.timestamp, 'unixepoch') AS INTEGER))
          AND EXISTS (SELECT 1 FROM dim_time t WHERE t.time_key=CAST(strftime('%H%M%S', s.timestamp, 'unixepoch') AS INTEGER))
        """,
        (run_id,),
    )
    rating_loaded = conn.total_changes - before
    conn.commit()

    before = conn.total_changes
    conn.execute(
        """
        INSERT OR IGNORE INTO fact_tag
        (tag_event_key, user_key, movie_key, user_tag_key, date_key, time_key,
         source_user_id, source_movie_id, tagged_at_unix, etl_run_id)
        SELECT 'ml20m:tags.csv:' || s.source_record_ordinal,
               u.user_key, m.movie_key, d.user_tag_key,
               CAST(strftime('%Y%m%d', s.timestamp, 'unixepoch') AS INTEGER),
               CAST(strftime('%H%M%S', s.timestamp, 'unixepoch') AS INTEGER),
               s.user_id, s.movie_id, s.timestamp, ?
        FROM stg_user_tag s
        JOIN dim_user u ON u.user_id=s.user_id
        JOIN dim_movie m ON m.movie_id=s.movie_id AND m.is_current=1
        JOIN dim_user_tag d ON d.tag_key_norm=s.tag_key_norm
        WHERE s.reject_reason IS NULL
        """,
        (run_id,),
    )
    tag_loaded = conn.total_changes - before
    conn.commit()

    before = conn.total_changes
    conn.execute(
        """
        INSERT OR IGNORE INTO fact_genome_score(movie_key, genome_tag_key, relevance, etl_run_id)
        SELECT m.movie_key, g.genome_tag_key, s.relevance, ?
        FROM stg_genome_score s
        JOIN dim_movie m ON m.movie_id=s.movie_id AND m.is_current=1
        JOIN dim_genome_tag g ON g.source_tag_id=s.tag_id
        WHERE s.reject_reason IS NULL
        ORDER BY s.source_record_ordinal
        """,
        (run_id,),
    )
    genome_loaded = conn.total_changes - before
    conn.commit()

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS ix_fact_rating_movie_date ON fact_rating(movie_key, date_key);
        CREATE INDEX IF NOT EXISTS ix_fact_rating_user_date ON fact_rating(user_key, date_key);
        CREATE INDEX IF NOT EXISTS ix_fact_tag_movie_date ON fact_tag(movie_key, date_key);
        CREATE INDEX IF NOT EXISTS ix_fact_tag_text_date ON fact_tag(user_tag_key, date_key);
        """
    )
    conn.commit()
    return {
        "fact_rating": rating_loaded,
        "fact_tag": tag_loaded,
        "fact_genome_score": genome_loaded,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--wikidata-audit", type=Path, default=DEFAULT_WIKIDATA)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--chunk-size", type=int, default=BATCH_SIZE)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--replace", action="store_true", help="rebuild the generated database from raw inputs")
    mode.add_argument("--incremental", action="store_true", help="refresh sources and preserve warehouse history")
    args = parser.parse_args()
    if args.chunk_size <= 0:
        parser.error("--chunk-size must be positive")

    paths = {
        "movies.csv": args.raw_dir / "movies.csv",
        "links.csv": args.raw_dir / "links.csv",
        "ratings.csv": args.raw_dir / "ratings.csv",
        "tags.csv": args.raw_dir / "tags.csv",
        "genome-tags.csv": args.raw_dir / "genome-tags.csv",
        "genome-scores.csv": args.raw_dir / "genome-scores.csv",
        "wikidata_audit.json": args.wikidata_audit,
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise RuntimeError("Missing required inputs: " + ", ".join(missing))

    database = args.database
    database.parent.mkdir(parents=True, exist_ok=True)
    if database.exists() and not args.incremental:
        if not args.replace:
            raise RuntimeError(
                f"Warehouse already exists at {database}; use --incremental to refresh "
                "it or --replace to rebuild this generated database."
            )
        database.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(database) + suffix)
            if sidecar.exists():
                sidecar.unlink()

    run_at = utc_now()
    source_manifest = {
        name: {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
               "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for name, path in paths.items()
    }
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=FILE")
    conn.execute("PRAGMA cache_size=-100000")
    conn.executescript((ROOT / "sql/000_staging_schema.sql").read_text(encoding="utf-8"))
    conn.executescript((ROOT / "sql/001_warehouse_schema.sql").read_text(encoding="utf-8"))
    if args.incremental:
        for table in (
            "stg_movie", "stg_link", "stg_rating", "stg_user_tag",
            "stg_genome_tag", "stg_genome_score", "stg_wikidata_movie",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()

    cursor = conn.execute(
        "INSERT INTO etl_run(started_at_utc, code_version, source_manifest_json, run_status) "
        "VALUES (?, ?, ?, 'running')",
        (run_at, "movie-warehouse-etl-v1", json.dumps(source_manifest, sort_keys=True)),
    )
    run_id = int(cursor.lastrowid)
    conn.commit()

    stage_metrics: dict[str, tuple[int, int, int]] = {}
    loaded_metrics: dict[str, int] = {}
    try:
        transforms = [
            ("movies.csv", {"movieId", "title", "genres"}, "stg_movie", parse_movie),
            ("links.csv", {"movieId", "imdbId", "tmdbId"}, "stg_link", parse_link),
            ("ratings.csv", {"userId", "movieId", "rating", "timestamp"}, "stg_rating", parse_rating),
            ("tags.csv", {"userId", "movieId", "tag", "timestamp"}, "stg_user_tag", parse_user_tag),
            ("genome-tags.csv", {"tagId", "tag"}, "stg_genome_tag", parse_genome_tag),
            ("genome-scores.csv", {"movieId", "tagId", "relevance"}, "stg_genome_score", parse_genome_score),
        ]
        insert_sql = {
            "stg_movie": "INSERT INTO stg_movie VALUES (?, ?, ?, ?, ?)",
            "stg_link": "INSERT INTO stg_link VALUES (?, ?, ?, ?, ?)",
            "stg_rating": "INSERT INTO stg_rating VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            "stg_user_tag": "INSERT INTO stg_user_tag VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            "stg_genome_tag": "INSERT INTO stg_genome_tag VALUES (?, ?, ?, ?, ?)",
            "stg_genome_score": "INSERT INTO stg_genome_score VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        }
        for name, fields, table, transform in transforms:
            stage_metrics[name] = insert_csv_stage(
                conn, run_id, paths[name], fields, insert_sql[table], transform, args.chunk_size
            )
        wikidata_records, wikidata_metrics = load_wikidata_stage(
            conn, run_id, paths["wikidata_audit.json"]
        )

        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS ix_stg_rating_movie ON stg_rating(movie_id);
            CREATE INDEX IF NOT EXISTS ix_stg_rating_user ON stg_rating(user_id);
            CREATE INDEX IF NOT EXISTS ix_stg_user_tag_movie ON stg_user_tag(movie_id);
            CREATE INDEX IF NOT EXISTS ix_stg_genome_score_pair ON stg_genome_score(movie_id, tag_id);
            """
        )
        conn.commit()

        for source, table in (("ratings.csv", "stg_rating"), ("tags.csv", "stg_user_tag")):
            unmatched = count_rows(
                conn,
                f"SELECT COUNT(*) FROM {table} s WHERE s.reject_reason IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM stg_movie m WHERE m.movie_id=s.movie_id AND m.reject_reason IS NULL)",
            )
            if unmatched:
                for (ordinal, movie_id) in conn.execute(
                    f"SELECT source_record_ordinal, movie_id FROM {table} s "
                    "WHERE s.reject_reason IS NULL AND NOT EXISTS "
                    "(SELECT 1 FROM stg_movie m WHERE m.movie_id=s.movie_id AND m.reject_reason IS NULL)"
                ):
                    issue(conn, run_id, source, str(ordinal), "unknown_movie_id", str(movie_id))
                conn.commit()

        conn.execute(
            "INSERT OR IGNORE INTO dim_user(user_id) "
            "SELECT user_id FROM stg_rating WHERE reject_reason IS NULL "
            "UNION SELECT user_id FROM stg_user_tag WHERE reject_reason IS NULL ORDER BY user_id"
        )
        for row in conn.execute(
            "SELECT source_record_ordinal, tag_id, tag_text FROM stg_genome_tag "
            "WHERE reject_reason IS NULL ORDER BY source_record_ordinal"
        ):
            conn.execute(
                "INSERT OR IGNORE INTO dim_genome_tag(source_tag_id, tag_text) VALUES (?, ?)",
                (row["tag_id"], row["tag_text"]),
            )
        tag_values = conn.execute(
            "SELECT DISTINCT tag_text FROM stg_user_tag WHERE reject_reason IS NULL ORDER BY tag_text"
        )
        for (tag_text,) in tag_values:
            norm = normalized_tag(tag_text)
            if norm:
                conn.execute(
                    "INSERT OR IGNORE INTO dim_user_tag(tag_text, tag_key_norm) VALUES (?, ?)",
                    (tag_text, norm),
                )
        conn.commit()

        movie_keys, movie_versions_loaded = load_movie_dimension(conn, run_at, wikidata_records)
        prepare_date_and_time_dimensions(conn)
        loaded_metrics = build_facts(conn, run_id)

        accepted = {name: values[1] for name, values in stage_metrics.items()}
        rejected = {name: values[2] for name, values in stage_metrics.items()}
        source_rows = {name: values[0] for name, values in stage_metrics.items()}
        duplicates = {
            "movies.csv": duplicate_excess(conn, "stg_movie", "movie_id"),
            "links.csv": duplicate_excess(conn, "stg_link", "movie_id"),
            "ratings.csv": 0,
            "tags.csv": 0,
            "genome-tags.csv": duplicate_excess(conn, "stg_genome_tag", "tag_id"),
            "genome-scores.csv": duplicate_excess(conn, "stg_genome_score", "movie_id, tag_id"),
        }
        unmatched = {
            "movies.csv": 0,
            "links.csv": count_rows(
                conn,
                "SELECT COUNT(*) FROM stg_link l WHERE l.reject_reason IS NULL AND NOT EXISTS "
                "(SELECT 1 FROM stg_movie m WHERE m.movie_id=l.movie_id AND m.reject_reason IS NULL)",
            ),
            "ratings.csv": count_rows(
                conn,
                "SELECT COUNT(*) FROM stg_rating s WHERE s.reject_reason IS NULL AND NOT EXISTS "
                "(SELECT 1 FROM stg_movie m WHERE m.movie_id=s.movie_id AND m.reject_reason IS NULL)",
            ),
            "tags.csv": count_rows(
                conn,
                "SELECT COUNT(*) FROM stg_user_tag s WHERE s.reject_reason IS NULL AND NOT EXISTS "
                "(SELECT 1 FROM stg_movie m WHERE m.movie_id=s.movie_id AND m.reject_reason IS NULL)",
            ),
            "genome-tags.csv": 0,
            "genome-scores.csv": count_rows(
                conn,
                "SELECT COUNT(*) FROM stg_genome_score s WHERE s.reject_reason IS NULL AND "
                "(NOT EXISTS (SELECT 1 FROM stg_movie m WHERE m.movie_id=s.movie_id AND m.reject_reason IS NULL) "
                "OR NOT EXISTS (SELECT 1 FROM stg_genome_tag g WHERE g.tag_id=s.tag_id AND g.reject_reason IS NULL))",
            ),
        }
        # Source-to-target audit: rows unmatched to movie metadata are counted explicitly.
        for source, table, target in (
            ("movies.csv", "stg_movie", movie_versions_loaded),
            ("links.csv", "stg_link", movie_versions_loaded),
            ("ratings.csv", "stg_rating", loaded_metrics["fact_rating"]),
            ("tags.csv", "stg_user_tag", loaded_metrics["fact_tag"]),
            ("genome-tags.csv", "stg_genome_tag", count_rows(conn, "SELECT COUNT(*) FROM dim_genome_tag")),
            ("genome-scores.csv", "stg_genome_score", loaded_metrics["fact_genome_score"]),
        ):
            rows = source_rows[source]
            accepted_rows = accepted[source]
            rejected_rows = rejected[source]
            duplicate_rows = duplicates[source]
            unmatched_rows = unmatched[source]
            save_table_audit(
                conn, run_id, source, rows, accepted_rows, rejected_rows,
                duplicate_rows, unmatched_rows, target,
            )

        wikidata_loaded = count_rows(
            conn,
            "SELECT COUNT(*) FROM stg_wikidata_movie WHERE match_status='matched' "
            "AND EXISTS (SELECT 1 FROM dim_movie m WHERE m.movie_id=stg_wikidata_movie.movie_id AND m.is_current=1)",
        )
        matched_qid_counts = Counter(
            record.get("wikidataQid")
            for record in wikidata_records.values()
            if record.get("matchStatus") == "matched"
        )
        duplicate_qid_rows = sum(count - 1 for count in matched_qid_counts.values() if count > 1)
        save_table_audit(
            conn,
            run_id,
            "Wikidata",
            wikidata_metrics["sourceRows"],
            wikidata_metrics["acceptedRows"],
            wikidata_metrics["rejectedRows"],
            duplicate_qid_rows,
            wikidata_metrics["unmatchedRows"] + wikidata_metrics["ambiguousRows"],
            wikidata_loaded,
        )
        wikidata_metrics["loadedRows"] = wikidata_loaded
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_stg_wikidata_qid ON stg_wikidata_movie(wikidata_qid)"
        )
        conn.commit()

        counts = {
            table: count_rows(conn, f"SELECT COUNT(*) FROM {table}")
            for table in (
                "stg_movie", "stg_link", "stg_rating", "stg_user_tag",
                "stg_genome_tag", "stg_genome_score", "stg_wikidata_movie",
                "dim_user", "dim_movie", "dim_date", "dim_time", "dim_genre",
                "dim_language", "dim_country", "dim_person", "dim_user_tag",
                "dim_genome_tag", "bridge_movie_genre", "bridge_movie_language",
                "bridge_movie_country", "bridge_movie_director", "fact_rating",
                "fact_tag", "fact_genome_score", "etl_quality_issue", "etl_table_audit",
            )
        }
        fk_violations = []
        fk_violation_count = 0
        for violation in conn.execute("PRAGMA foreign_key_check"):
            fk_violation_count += 1
            if len(fk_violations) < 100:
                fk_violations.append(tuple(violation))
        quality = {
            "foreignKeyViolationsSample": fk_violations,
            "foreignKeyViolationCount": fk_violation_count,
            "ratingsOutsideRange": count_rows(
                conn, "SELECT COUNT(*) FROM fact_rating WHERE rating < 0.5 OR rating > 5.0"
            ),
            "genomeScoresOutsideRange": count_rows(
                conn, "SELECT COUNT(*) FROM fact_genome_score WHERE relevance < 0 OR relevance > 1"
            ),
            "moviesWithoutCurrentVersion": count_rows(
                conn,
                "SELECT COUNT(*) FROM stg_movie s WHERE s.reject_reason IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM dim_movie d WHERE d.movie_id=s.movie_id AND d.is_current=1)",
            ),
            "wikidataAmbiguousNotLoadedAsQid": count_rows(
                conn,
                "SELECT COUNT(*) FROM stg_wikidata_movie w JOIN dim_movie m ON m.movie_id=w.movie_id AND m.is_current=1 "
                "WHERE w.match_status='ambiguous' AND m.wikidata_qid IS NOT NULL",
            ),
        }
        conn.execute(
            "UPDATE etl_run SET completed_at_utc=?, run_status='succeeded' WHERE run_id=?",
            (utc_now(), run_id),
        )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.commit()
        report = {
            "runId": run_id,
            "status": "succeeded",
            "startedAtUtc": run_at,
            "completedAtUtc": utc_now(),
            "database": str(database.relative_to(ROOT)) if database.is_relative_to(ROOT) else str(database),
            "databaseBytes": database.stat().st_size,
            "inputs": source_manifest,
            "wikidataMatchSummary": wikidata_metrics,
            "counts": counts,
            "quality": quality,
            "tableAudit": [dict(row) for row in conn.execute(
                "SELECT table_name AS tableName, source_rows AS sourceRows, accepted_rows AS acceptedRows, "
                "rejected_rows AS rejectedRows, duplicate_rows AS duplicateRows, unmatched_rows AS unmatchedRows, "
                "loaded_rows AS loadedRows FROM etl_table_audit WHERE run_id=? ORDER BY table_name",
                (run_id,),
            )],
        }
        args.report_dir.mkdir(parents=True, exist_ok=True)
        report_path = args.report_dir / f"etl_run_{run_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"Saved ETL report to {report_path.relative_to(ROOT) if report_path.is_relative_to(ROOT) else report_path}")
        conn.close()
        return 0
    except Exception as error:
        conn.execute(
            "UPDATE etl_run SET completed_at_utc=?, run_status='failed' WHERE run_id=?",
            (utc_now(), run_id),
        )
        conn.commit()
        conn.close()
        raise RuntimeError(f"ETL run {run_id} failed: {error}") from error


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, sqlite3.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
