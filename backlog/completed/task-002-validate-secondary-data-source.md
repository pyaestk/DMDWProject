# TASK-002: Select and validate an independent movie metadata source

**Status:** Done  
**Owner:** Team  
**Course milestone:** Data acquisition and warehouse build  
**Target date:** 2026-10-05

## Goal

Select one genuinely independent movie-metadata source and confirm that it can
be joined to MovieLens through a documented identifier.

## Completion summary

- Selected Wikidata as the secondary source; documented CC0 terms, suggested
  source attribution, the `P345` IMDb ID crosswalk, and the fields to pilot in
  `docs/source-register.md` and
  `docs/decisions/2026-09-28-wikidata-secondary-source.md`.
- Measured a deterministic random sample of 100 MovieLens movies (seed 544):
  96 matched Wikidata IDs, 4 were unmatched, and none were ambiguous.
- Among the 96 matched sample records, the observed counts were 96 release
  dates, 96 original languages, 95 directors, 88 runtimes, 96 countries, and
  93 genres.
- Saved the sample-level crosswalk and field-coverage results to
  `outputs/source_audit/wikidata_match_pilot_2026-09-28.json`.
- Added `tools/wikidata_match_pilot.py` to reproduce the bounded lookup.

## Acceptance criteria

- [x] An independent provider is selected and cited.
- [x] Academic-use terms and attribution expectations are recorded.
- [x] Crosswalk method and pilot match rate are measured and recorded.
- [x] Unmatched records are retained with null external attributes; they are
      not silently dropped.
- [x] Pilot fields are assigned to the movie metadata dimension. They are not
      yet approved as H2/H3 model features.

## Verification performed

- Queried the Wikidata GraphQL `itemByExternalId` operation using P345 for a
  deterministic 100-title sample from MovieLens `links.csv`.
- Reviewed the output counts and saved the result. Full-catalog coverage and
  the production ETL have not yet been run.

## Limitations

- The 100-title match rate is an initial estimate, not a full-catalog result.
- Wikidata metadata is community maintained; field completeness and correctness
  require checks in the full load.
