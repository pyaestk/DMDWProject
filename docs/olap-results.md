# OLAP execution results

The five planned OLAP analyses were executed against
`data/warehouse/movie_preference.sqlite` on 2026-09-28. The executable notebook
is [`notebooks/olap_analysis.ipynb`](../notebooks/olap_analysis.ipynb); the
machine-readable results and query plans are in
[`outputs/olap/olap_run.json`](../outputs/olap/olap_run.json).

## Environment and method

- Database: 5,700,124,672 bytes (about 5.7 GB), with 20,000,263 rating facts
  and 465,557 accepted tag facts.
- Runtime: macOS 26.5.1, arm64; Python 3.14.3; SQLite 3.50.4.
- Each query was run once, sequentially, through a read-only SQLite connection.
  Timing uses `perf_counter` around SQL execution and fetching every result
  row. SQLite and OS caches were left in their default state; no cache flush or
  warm-up was used. The measured order is Q1, Q2, Q3, Q4, Q5, then Q5 coverage.
- The notebook cells were executed sequentially in one Python process because
  the sandbox prevented its normal Jupyter kernel launcher from opening a
  local connection. The notebook retains its code and outputs and can also be
  rerun with a normal Python 3 Jupyter kernel.

## Measured query results

| Analysis | OLAP operation | Result rows | Elapsed seconds |
| --- | --- | ---: | ---: |
| Q1: year/month by MovieLens genre | Month drill-down plus year roll-up | 4,792 | 162.935 |
| Q2: genre by user activity band | Slice to UTC 2010–2015; pivot low/medium/high activity bands | 20 | 25.890 |
| Q3: highest and lowest genres by year | Rank yearly genre averages; minimum 1,000 ratings per genre/year | 40 | 81.855 |
| Q4: tag applications by genre and year | Aggregate user-applied tag events | 324,427 | 2.268 |
| Q5: Wikidata country by release decade | Country and release-decade breakdown | 590 | 134.937 |
| Q5 coverage companion | Count catalog movies and rating events with/without exact Wikidata and country matches | 3 | 0.799 |

Combined elapsed time for the five primary queries and the Q5 coverage summary
was 408.683 seconds (about 6 minutes 49 seconds) in this run. These figures
describe this environment and cache state; they are not universal performance
benchmarks.

## Wikidata coverage used by Q5

| Coverage group | Movies | Movies with ratings | Rating events |
| --- | ---: | ---: | ---: |
| Exact Wikidata match with country | 26,232 | 25,743 | 19,982,080 |
| Exact Wikidata match without country | 31 | 29 | 257 |
| No exact match (unmatched or ambiguous) | 1,015 | 972 | 17,926 |

The event totals sum to 20,000,263, the complete rating fact count. “No exact
match” combines 981 unmatched and 34 ambiguous Wikidata outcomes; ambiguous
candidates were not assigned to the movie dimension. Country is multivalued,
so a movie with multiple Wikidata countries contributes its rating events to
each country group. Do not sum country rows as though countries partition the
catalog.

## Index and query-plan observations

The notebook records the full `EXPLAIN QUERY PLAN` output for every query.
SQLite used the bridge primary-key indexes to look up movie genres/countries.
Q2 used `ix_fact_rating_user_date` to calculate user rating activity and
retrieve ratings by user. Q5 used `ix_fact_rating_movie_date` to aggregate
ratings by movie, and the country bridge's movie-key index. Full-catalog
queries Q1 and Q3 scanned the rating fact table and built temporary B-trees
for grouping/ranking; Q4 scanned the tag fact table and used a temporary
B-tree to group/order its high-cardinality result. No additional indexes or
partitioning were introduced for these measurements.

## Interpretation notes

- Genre and country are multivalued classifications. Rating counts grouped by
  these dimensions are counts per classification and can exceed the overall
  fact count when summed across categories.
- User activity bands are descriptive segments calculated from each user's
  complete rating history; they are not safe future-only features for H3
  prediction.
- Wikidata metadata is the current retrieved snapshot, not a historical record
  of what was known when ratings were created.
- Q4 reports tag application events; it does not measure views or movie
  popularity.
