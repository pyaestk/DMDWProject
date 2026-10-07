# 2026-09-28: Select Wikidata as the secondary movie metadata source

**Status:** Selected; full-catalog matching audit completed, warehouse loading
pending.  
**Decision owner:** Team

## Decision

Use Wikidata as the project's secondary movie-metadata source, matched through
IMDb identifiers in MovieLens `links.csv`. Use matched values to enrich the
movie dimension. Keep all MovieLens records, including movies that do not
match Wikidata.

## Why

- Wikidata publishes its structured data under CC0. It suggests attribution,
  even though attribution is not required.
- Wikidata has an IMDb external-identifier property (P345) and supports exact
  lookups by external identifier.
- The deterministic random pilot matched 96/100 sampled titles (96%), with no
  ambiguous IDs. This is promising but not a full-catalog coverage estimate.
- TMDb was not selected because its current API terms prohibit using TMDb
  content in connection with machine-learning applications, while this project
  includes H2 clustering and H3 rating prediction.

## Pilot evidence

- Input: 100 MovieLens `links.csv` rows with a nonzero IMDb ID.
- Sampling: Python `random.Random(544).sample`, seed 544; sample run on
  2026-09-28.
- Key normalization: prefix MovieLens's numeric IMDb ID with `tt` and left-pad
  to at least seven digits.
- Lookup: Wikidata GraphQL `itemByExternalId(property: "P345", ...)`.
- Result: 96 matched; 4 unmatched; 0 ambiguous. Attribute counts among matched
  items: release date 96, original language 96, director 95, runtime 88,
  country 96, genre 93.
- Reproducible output:
  `outputs/source_audit/wikidata_match_pilot_2026-09-28.json`.
- Reproduction script: `tools/wikidata_match_pilot.py`.

## Full-catalog matching evidence

- Audited all 27,278 `links.csv` rows with nonzero IMDb IDs on 2026-09-28.
- Exact matches: 26,263 (96.28%); unmatched: 981 (3.60%); ambiguous: 34
  (0.12%). The ambiguity cases remain unresolved and are excluded from
  automatic enrichment.
- Exact matches represent 26,262 unique QIDs. One QID is shared by two
  MovieLens records for *The Testament of Dr. Mabuse*; keep both movie IDs and
  their separate rating histories.
- Among exact matches, field coverage is: release date 99.01%, original
  language 96.40%, director 98.62%, runtime 91.89%, country 99.88%, and genre
  97.47%.
- Full result:
  `outputs/source_audit/wikidata_match_full_catalog_2026-09-28.json`.
- Re-run/resume command:
  `python3 tools/wikidata_match_pilot.py --full-catalog --batch-size 50 --delay-seconds 5 --resume --output outputs/source_audit/wikidata_match_full_catalog_2026-09-28.json`.

## Use and limits

- Store the selected fields as movie-level metadata with the Wikidata QID and
  retrieval date for lineage.
- Treat unmatched external attributes as missing; do not delete the movie.
- The initial 100-title pilot is superseded for coverage estimates by the
  full-catalog matching audit above. Recheck coverage if a later source
  snapshot or matching rule changes.
- The pilot data does not establish that external attributes improve H2 or H3.
  The baseline mining features remain based on MovieLens until any extension is
  separately evaluated.

## References

- [Wikidata reuse and data access](https://www.wikidata.org/wiki/Wikidata:Reuse)
- [IMDb ID property P345](https://www.wikidata.org/wiki/Property:P345)
- [Wikibase GraphQL external-ID lookup](https://www.wikidata.org/wiki/Wikidata:Wikibase_GraphQL)
- [TMDb API terms](https://www.themoviedb.org/api-terms-of-use)
