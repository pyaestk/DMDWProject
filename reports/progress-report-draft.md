# Movie Preference Analysis: Progress Report Draft

**Course:** ITCS544 Data Mining and Data Warehousing  
**Data snapshot:** MovieLens 20M plus Wikidata metadata, extracted/loaded 2026-09-28  
**Status:** Technical progress draft; all numerical results below link to saved run evidence.

## 1. Project overview

This project builds a reproducible warehouse for movie ratings and metadata,
then applies multidimensional OLAP and preliminary mining to user behavior.
The project combines MovieLens 20M with Wikidata movie descriptions matched
through IMDb identifiers. MovieLens remains the source of rating events,
user-applied tags, genres, and tag-genome relevance scores. Wikidata enriches
movie-level release, language, director, runtime, country, and genre metadata.

The progress-report work has implemented and loaded the staging and
dimensional warehouse, documented fact and dimension grains, executed five
OLAP analyses, and run an initial H2 user clustering and H3 rating-baseline
pipeline. Final supervised-model selection and tuning remain future work.

## 2. Sources, architecture, and dimensional model

The six MovieLens CSVs are related files from one provider and are treated as
one source. Wikidata is the independent secondary source. Of 27,278 MovieLens
crosswalk rows with a nonzero IMDb ID, 26,263 matched exactly to Wikidata
(96.28%), 981 were unmatched, and 34 were ambiguous. Unmatched and ambiguous
records remain in staging/audit and do not receive an automatically assigned
Wikidata QID.

The implemented flow is:

```text
MovieLens CSVs ─┐
                ├─> source staging + validation/audit ─> SQLite dimensional warehouse
Wikidata data ──┘
```

The physical prototype currently has staging tables and the dimensional
warehouse in SQLite. A separately materialized enterprise data mart layer is
not present in this prototype. The logical ERD, relationship sketch, source
mapping, and full bus matrix are in
[`docs/warehouse-design.md`](../docs/warehouse-design.md); physical table
definitions are in [`sql/001_warehouse_schema.sql`](../sql/001_warehouse_schema.sql).

| Fact table | Grain | Key dimensions and measures |
| --- | --- | --- |
| `fact_rating` | One user rating of one movie at one Unix timestamp | User, movie, UTC date/time; rating value; source-row lineage key |
| `fact_tag` | One user-applied tag to one movie at one timestamp | User, movie, tag, UTC date/time; source-row lineage key |
| `fact_genome_score` | One MovieLens movie and one genome tag | Movie, genome tag; relevance from 0 to 1 |

Core dimensions include user, Type 2 movie, date, time, genre, user tag,
genome tag, language, country, and director/person. Genre, language, country,
and director relationships use bridge tables so multi-valued movie metadata
does not multiply stored rating rows. Type 2 movie history is implemented for
changes observed between warehouse loads; only one metadata snapshot has been
loaded so far, so no historical change has yet been observed. Rating and tag
event lineage keys serve as technical degenerate dimensions because their
publisher files have no event identifier.

| Business process / fact | User | Movie | Date | Time | Genre | User tag | Genome tag | Wikidata language/country/director |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Rating event | ✓ | ✓ | ✓ | ✓ | via movie bridge |  |  | via movie bridges |
| User tag event | ✓ | ✓ | ✓ | ✓ | via movie bridge | ✓ |  | via movie bridges |
| Genome relevance |  | ✓ |  |  | via movie bridge |  | ✓ | via movie bridges |

## 3. ETL execution and quality

The automated Python/SQLite ETL validates source headers and parsed values,
loads every source row to staging with lineage, creates conformed dimensions
and bridges, loads separate fact tables, and records run manifests and quality
issues. Rebuild and incremental commands are documented in
[`docs/etl-runbook.md`](../docs/etl-runbook.md). Raw source files were left
unchanged.

| Source | Input/staged rows | Loaded rows | Rejected/unresolved |
| --- | ---: | ---: | ---: |
| Ratings | 20,000,263 | 20,000,263 | 0 rejected; no out-of-range ratings |
| User tags | 465,564 | 465,557 | 7 blank tag events rejected; preserved in staging and issue records |
| Genome scores | 11,709,768 | 11,709,768 | 0 rejected |
| Wikidata crosswalk results | 27,278 | 26,263 exact enrichments | 981 unmatched; 34 ambiguous |

The loaded warehouse has 138,493 users, 27,278 current movies, 20,000,263
rating facts, 465,557 tag facts, and 11,709,768 genome-score facts. Rating
values and genome relevance values passed their range checks. No duplicate
MovieLens natural keys were found in the audited files, and the recorded
foreign-key violation count is zero. No numeric imputation was applied to
rating events. Blank tag text is not a valid tag value, so those seven records
were rejected from `fact_tag`; missing Wikidata descriptions remain null or
absent in the relevant bridges. The full ETL metrics and source fingerprints
are in [`outputs/etl/etl_run_1_20260928T150023Z.json`](../outputs/etl/etl_run_1_20260928T150023Z.json).

## 4. OLAP benchmark

Five multidimensional analyses ran against the 5.7 GB SQLite warehouse. The
measured full-query times, result counts, hardware/software versions, and
`EXPLAIN QUERY PLAN` summaries are documented in
[`docs/olap-results.md`](../docs/olap-results.md) and
[`notebooks/olap_analysis.ipynb`](../notebooks/olap_analysis.ipynb).

| Query | Analysis | Result rows | Time (sec) |
| --- | --- | ---: | ---: |
| Q1 | Rating count/mean by year/month and MovieLens genre; month drill-down/year roll-up | 4,792 | 162.935 |
| Q2 | Genre pivoted across user activity bands, sliced to UTC 2010–2015 | 20 | 25.890 |
| Q3 | Highest/lowest average-rated genre by year, at least 1,000 ratings per group | 40 | 81.855 |
| Q4 | User-applied tag applications by tag, genre, and year | 324,427 | 2.268 |
| Q5 | Rating activity and average by Wikidata country and release decade | 590 | 134.937 |

SQLite used `ix_fact_rating_user_date` for user-history analysis,
`ix_fact_rating_movie_date` for movie-level rating aggregation, and primary
indexes on the movie bridges. Full-period scans used temporary B-trees for
grouping/ranking. The prototype does not use physical table partitioning;
SQLite does not provide native table partitioning, so this is a documented
engine limitation rather than a measured partitioning optimization. The
benchmark used one sequential pass with default SQLite/OS caches and no
warm-up or cache flush; times are specific to the recorded environment.

## 5. Preliminary mining pipeline and EDA

The executed notebook and machine-readable output are
[`notebooks/mining_preliminary.ipynb`](../notebooks/mining_preliminary.ipynb)
and [`outputs/mining/preliminary_run.json`](../outputs/mining/preliminary_run.json).
Ratings span 1995-01-09 through 2015-03-31 UTC. Rating 4.0 was the most common
value (5,561,926 events). Median user activity was 68 ratings (90th percentile
334); among movies with ratings, the median movie activity was 18 ratings
(90th percentile about 1,306).
EDA charts are included in the notebook and saved as
[`ratings overview`](../outputs/mining/eda_ratings_overview.png) and
[`movie activity`](../outputs/mining/eda_movie_activity.png).

### H2: initial user clusters

The analysis unit is the user. The 24 standardized features comprise log
rating count, average rating, rating standard deviation, share of ratings at
least 4.0, and rating-event shares over 20 MovieLens genres. K-means candidates
k=2, 3, and 4 were compared on a seeded 25,000-user sample; the corresponding
sampled silhouette scores were 0.1170, 0.1148, and 0.0896. The k=2 model was
fit on all 138,493 users and had a sampled silhouette of 0.1104.

The resulting clusters contain 49,938 and 88,555 users. Their mean ratings
(3.593 and 3.647) and high-rating shares (53.6% and 55.7%) are similar. The
clusters differ somewhat in their largest genre shares, but the silhouette
indicates weak separation; these results are exploratory and do not establish
distinct user archetypes.

### H3: time-based rating baselines

The cutoff is 2010-01-01 UTC: 16,152,716 earlier ratings supply training
statistics and 3,847,547 later ratings form the held-out test set. Global and
movie averages use training data only. Unseen test movies fall back to the
training global mean; this affected 588,406 test events.

| Baseline | Test events | RMSE | MAE |
| --- | ---: | ---: | ---: |
| Training global average | 3,847,547 | 1.0194 | 0.7899 |
| Training movie average, global fallback | 3,847,547 | 0.9460 | 0.7189 |

The movie-average baseline is better than the global baseline on this split.
No supervised feature model has yet been evaluated, so the project has not
established whether H3's proposed predictor beats its baselines. Candidate
features include train-only user history, movie rating activity/mean, and
MovieLens genres. Tag and genome coverage are partial; genome scores have no
event timestamp. Wikidata snapshot features were excluded from the baseline
because their temporal alignment to historical ratings is uncertain.

## 6. Next work within the progress-report stage

Review the preliminary notebook outputs, confirm the report's team details,
and format this draft to the course's eight-page maximum. Full supervised
model selection, tuning, ablations, and final H2/H3 conclusions are reserved
for the later mining milestone tracked in TASK-004.

## References

- GroupLens, [MovieLens 20M README and usage terms](https://files.grouplens.org/datasets/movielens/ml-20m-README.html).
- Wikidata, [Data access and reuse](https://www.wikidata.org/wiki/Wikidata:Reuse).
- Course requirements and source-use details are recorded in
  [`docs/course-requirements.md`](../docs/course-requirements.md) and
  [`docs/source-register.md`](../docs/source-register.md).
