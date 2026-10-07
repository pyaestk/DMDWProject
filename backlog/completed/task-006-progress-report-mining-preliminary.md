# TASK-006: Build preliminary mining evidence for the progress report

**Status:** Done  
**Owner:** Team  
**Course milestone:** Progress report  
**Target date:** 2026-10-13

## Goal

Prepare reproducible preliminary EDA, H2 clustering, and H3 baseline evidence
for the progress report using the validated warehouse.

## Scope

- Profile warehouse coverage and rating, user, genre, tag, and genome data.
- Build descriptive user-level rating and genre-share features and perform an
  initial clustering preview for H2.
- Evaluate global-average and movie-average H3 baselines on a documented
  chronological holdout, computing all movie averages from training data.
- Record the initial H3 feature strategy and leakage/coverage limitations.

Full predictor selection, tuning, and final evaluation remain in TASK-004.

## Acceptance criteria

- [x] A rerunnable notebook contains EDA and quality/coverage summaries.
- [x] H2 feature definitions, initial clusters, quality metric, and profiles
      are recorded.
- [x] H3 train/test cutoff and baseline RMSE/MAE are recorded with cold-start
      handling.
- [x] Results and runtime metadata are saved and referenced by report notes.
- [x] Raw data and warehouse remain unchanged.

## Verification plan

- Execute notebook cells against the warehouse opened read-only.
- Reconcile user/rating/movie counts with ETL evidence.
- Confirm train-only feature construction and compare evaluation counts.

## Completion notes

- Changed files/artifacts: `notebooks/mining_preliminary.ipynb`,
  `outputs/mining/preliminary_run.json`, two EDA figures,
  `docs/mining-preliminary-results.md`, and the progress-report draft in
  Markdown and PDF. Updated the warehouse/source documentation and this task.
- Verification actually performed: executed every notebook code cell against
  the warehouse opened read-only; reconciled ETL and fact counts; confirmed
  chronological train/test row counts; validated the notebook structure and
  JSON run record; rendered and inspected the 7-page PDF draft.
- Results and limitations: 138,493 users were clustered with standardized
  behavioral and genre-share features. Candidate k=2/3/4 sampled silhouettes
  were 0.1170/0.1148/0.0896; the k=2 full-data preview silhouette was 0.1104,
  indicating weak separation. On 3,847,547 held-out post-cutoff ratings, the
  global baseline had RMSE 1.0194 and MAE 0.7899; the movie-average baseline
  with global fallback had RMSE 0.9460 and MAE 0.7189. No supervised model has
  been evaluated; full model selection and tuning remain in TASK-004.
