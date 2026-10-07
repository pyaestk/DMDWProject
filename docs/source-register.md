# Data source register

| Source | Role | Identifier / join | Fields in scope | Terms / attribution | Status |
| --- | --- | --- | --- | --- | --- |
| MovieLens 20M (GroupLens) | Primary ratings, tags, movie catalog, and tag genome | `movieId`; external crosswalks in `links.csv` | Ratings, timestamps, genres, tags, genome scores, IDs | Research use under GroupLens conditions; acknowledge source and do not redistribute the dataset without permission | Local source available; raw files stay unchanged |
| Wikidata | Secondary movie metadata source | MovieLens `links.csv` IMDb ID normalized as `tt` + zero-padded ID; Wikidata property P345 | Release date (P577), original language (P364), director (P57), runtime (P2047), country (P495), genre (P136) | Structured data under CC0; attribution is not required but should be provided in reports | Full matching-frame audit and initial warehouse load completed 2026-09-28 |

## Full-catalog match audit (2026-09-28)

- Frame: all 27,278 `links.csv` rows with a nonzero IMDb ID. Movies without a
  usable IMDb ID are outside this match-rate denominator and remain in
  MovieLens.
- Exact Wikidata match: 26,263/27,278 (96.28%). Unmatched: 981 (3.60%).
  Ambiguous external-ID matches: 34 (0.12%). Unmatched and ambiguous records
  are not assigned a Wikidata entity automatically.
- The 26,263 matched MovieLens records refer to 26,262 unique Wikidata QIDs.
  One QID is shared by two MovieLens catalog entries for *The Testament of Dr.
  Mabuse*; retain both MovieLens records and report the shared mapping rather
  than collapsing their rating histories.
- Field coverage among the exact matched records: release date 26,003
  (99.01%); original language 25,317 (96.40%); director 25,900 (98.62%);
  runtime 24,132 (91.89%); country 26,232 (99.88%); genre 25,598 (97.47%).
- Reproducible result:
  `outputs/source_audit/wikidata_match_full_catalog_2026-09-28.json`.
  The JSONL checkpoint is retained alongside it. The audit uses exact
  Wikidata GraphQL P345 lookup and reports the retrieval date.

## Source-use boundaries

- MovieLens remains the source for user ratings and user-generated tags.
- Wikidata enriches movie-level descriptions in the warehouse. Unmatched
  MovieLens movies remain present with null Wikidata attributes.
- Exclude the 34 ambiguous IMDb-to-Wikidata lookups from automatic enrichment
  until they are reviewed; retain them in a match-audit table with their
  candidate QIDs.
- Do not treat Wikidata aggregate user ratings as MovieLens ratings.
- Do not use external metadata as a rating-prediction feature until the team
  documents temporal alignment and confirms the modeling decision.
- Do not use TMDb API content in H2/H3 model workflows without written
  permission; its current API terms prohibit use in connection with ML/AI
  applications.

## References

- [MovieLens 20M README and usage terms](https://files.grouplens.org/datasets/movielens/ml-20m-README.html)
- [Wikidata data access and reuse](https://www.wikidata.org/wiki/Wikidata:Reuse)
- [Wikidata IMDb ID property P345](https://www.wikidata.org/wiki/Property:P345)
- [Wikidata GraphQL exact external-ID lookup](https://www.wikidata.org/wiki/Wikidata:Wikibase_GraphQL)
- [TMDb API terms](https://www.themoviedb.org/api-terms-of-use)
