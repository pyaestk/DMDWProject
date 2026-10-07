# Preliminary mining results for the progress report

The reproducible analysis is in
[`notebooks/mining_preliminary.ipynb`](../notebooks/mining_preliminary.ipynb).
Machine-readable run evidence is in
[`outputs/mining/preliminary_run.json`](../outputs/mining/preliminary_run.json).
The notebook reads the existing warehouse in read-only mode. Its measured
environment, feature definitions, charts, cluster profiles, and baseline
metrics are saved with the executed cells.

## Data preparation and quality

The analysis uses the successful ETL output dated 2026-09-28:

| Source/input | Before transformation | Accepted/loaded | Rejected or unresolved |
| --- | ---: | ---: | ---: |
| MovieLens ratings | 20,000,263 | 20,000,263 rating facts | 0 rejected; 0 outside rating range |
| MovieLens user tags | 465,564 | 465,557 tag facts | 7 blank tag values rejected and retained in staging/issues |
| MovieLens genome scores | 11,709,768 | 11,709,768 genome-score facts | 0 rejected |
| Wikidata audit rows | 27,278 | 26,263 exact movie enrichments | 981 unmatched and 34 ambiguous; retained without assigning a QID |

No text or numeric imputation was applied to rating events for these
preliminary experiments. Blank user tags were treated as invalid tag events;
unavailable external metadata remains missing. The warehouse recorded zero
foreign-key violations. MovieLens contains 138,493 users, 27,278 movies, 20
MovieLens genres, and 11,709,768 genome-score rows. User tags cover 19,545
movies and 7,800 users; genome scores cover 10,381 movies. These coverage gaps
mean that absence of tags or genome rows must be treated as unknown, not as a
negative preference or zero relevance.

## Exploratory data analysis

The 20,000,263 ratings span 1995-01-09 through 2015-03-31 UTC. Rating 4.0 is
the most common value (5,561,926 events). The median user contributed 68
ratings (90th percentile: 334; maximum: 9,254). Among movies with at least one
rating, the median received 18 ratings (90th percentile: 1,306; maximum: 67,310). User and movie activity
are strongly right-skewed; the notebook includes rating-distribution,
rating-timeline, user-activity, and movie-activity plots. Counts grouped by
genre are per assigned genre and overlap because a movie may have multiple
genres.

## H2 preliminary user clustering

The analysis unit is a user. The feature matrix contains 138,493 users and 24
features: log rating count, mean rating, rating standard deviation, share of
ratings at least 4.0, and rating-event shares across the 20 MovieLens genres.
Each feature was standardized. Candidate k values 2, 3, and 4 were compared on
a deterministic 25,000-user sample (seed 544), with silhouette estimated from
a 1,500-user sample. The selected k=2 model was then fitted to all users; its
silhouette was estimated on a fixed 2,000-user sample.

| Candidate k | Sampled silhouette |
| ---: | ---: |
| 2 | 0.1170 |
| 3 | 0.1148 |
| 4 | 0.0896 |

The full-data k=2 fit had a sampled silhouette of 0.1104. Its preliminary
profiles are:

| Cluster | Users | Median rating events | Mean rating | Mean within-user rating SD | Share rating >= 4 | Highest genre shares |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | 49,938 | 65 | 3.593 | 0.968 | 53.6% | Comedy, Drama, Adventure |
| 1 | 88,555 | 69 | 3.647 | 0.930 | 55.7% | Drama, Comedy, Thriller |

The silhouette values indicate weak separation in this feature space, and the
two groups have similar average-rating behavior. Treat these as an initial
descriptive result, not confirmation of distinct preference archetypes.
TASK-004 can revisit feature weighting and cluster-count selection.

## H3 preliminary prediction baselines

The target is an individual rating. The chronological cutoff is 2010-01-01
UTC: 16,152,716 pre-cutoff events were used for training statistics and
3,847,547 events on/after the cutoff formed the test set. The global mean and
each movie's mean were computed from training events only. If a test movie had
no training ratings, its prediction fell back to the training global mean;
this covered 588,406 test events.

| Baseline | Test events | RMSE | MAE | Cold-start fallback events |
| --- | ---: | ---: | ---: | ---: |
| Training global mean | 3,847,547 | 1.0194 | 0.7899 | 0 |
| Training movie mean, global fallback | 3,847,547 | 0.9460 | 0.7189 | 588,406 |

On this split, the movie-average baseline performed better than the global
average baseline on both metrics. These are preliminary baseline results; no
supervised feature model has yet been evaluated. The planned feature strategy
adds training-only user history, movie activity/popularity, and MovieLens
genre indicators. Tag/genome features need explicit sparse-coverage handling;
genome scores lack event timestamps. Current Wikidata metadata was excluded
from this prediction baseline because it is a later metadata snapshot.

## Reproducibility and limitations

- Runtime environment: macOS 26.5.1 arm64; Python 3.14.3; SQLite 3.50.4;
  NumPy 2.4.4; pandas 3.0.2; scikit-learn 1.8.0; random seed 544.
- The warehouse was opened read-only. H2 describes complete observed user
  histories; it is not a time-forward prediction task.
- H3 uses a chronological holdout and training-only means. Final supervised
  model selection, feature ablations, and broader evaluation remain in
  TASK-004 for the later milestone.
- The notebook was executed sequentially in one Python process because the
  sandbox blocks starting a separate Jupyter kernel. Its saved cells and
  outputs can be rerun with a regular Python 3 Jupyter kernel.
