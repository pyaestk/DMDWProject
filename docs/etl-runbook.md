# Warehouse ETL Runbook

## Inputs

- Original MovieLens 20M CSVs in `ml-20m/` (read-only).
- Full-catalog Wikidata match audit in
  `outputs/source_audit/wikidata_match_full_catalog_2026-09-28.json`.
- Python standard library and SQLite; no extra package installation is needed.

The ETL run record captures SHA-256 hashes, byte sizes, and relative paths for
each source file in `etl_run.source_manifest_json`.

## Build or rebuild

Build the default warehouse when no database exists:

```bash
python3 tools/build_warehouse.py
```

Rebuild the generated warehouse from the current inputs:

```bash
python3 tools/build_warehouse.py --replace
```

Refresh staging and append newly observed facts while preserving existing fact
rows and Type 2 movie history:

```bash
python3 tools/build_warehouse.py --incremental
```

The generated database is `data/warehouse/movie_preference.sqlite`. Each run
writes a JSON evidence report under `outputs/etl/`. Do not commit the
multi-gigabyte warehouse unless the team agrees to store generated data in Git.

## What the loader does

1. Checks required files and exact CSV columns, fingerprints each input, and
   creates a run record.
2. Loads one staging row for every source data record, including original
   values, parsed values, source-record ordinal, and validation reason.
3. Stages every Wikidata audit outcome. Exact matches enrich `dim_movie`;
   unmatched and ambiguous records remain in staging and the issue table.
4. Loads conformed dimensions and bridges, then separate rating, user-tag, and
   genome-score fact tables.
5. Uses source file plus record ordinal as a degenerate lineage key for rating
   and user-tag facts.
6. Records source and target counts, rejected/duplicate/unmatched rows, file
   hashes, quality checks, and foreign-key violations.

## First-run evidence (2026-09-28)

The first run is `outputs/etl/etl_run_1_20260928T150023Z.json`. It staged
20,000,263 ratings, 465,564 user tags, 11,709,768 genome scores, 27,278 movies,
27,278 crosswalk rows, 1,128 genome tags, and 27,278 Wikidata lookup results.
The warehouse contains 20,000,263 ratings, 465,557 tag events, and 11,709,768
genome scores. Seven blank tag records remain in staging and issue records;
they are excluded from `fact_tag`. The load records zero foreign-key
violations and no unmatched references in the loaded facts. Wikidata had
26,263 exact matches, 981 unmatched IDs, and 34 ambiguous IDs; ambiguous
candidates are retained but not assigned to the movie dimension.

Full Wikidata field coverage and limitations are documented in
`source-register.md`. OLAP execution and runtimes are not part of this load.
