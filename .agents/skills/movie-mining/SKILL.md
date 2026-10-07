---
name: movie-mining
description: Plan, implement, or evaluate clustering, rating prediction, association, or anomaly mining using the validated movie warehouse.
---

# Movie mining workflow

Use this skill for feature engineering, mining algorithms, baselines,
evaluation, and result interpretation.

## Steps

1. Read `AGENTS.md`, the active backlog task, the course assignment, and the
   warehouse table-grain documentation.
2. Implement the two agreed mining categories: H2 user clustering and H3
   rating prediction, unless the team and instructor explicitly revise scope.
3. State the analysis unit, research question, target (if any), features, and
   excluded fields.
4. Choose and document a split strategy before computing history, popularity,
   or aggregate features.
5. Establish simple baselines before fitting the proposed method.
6. Select metrics appropriate to the task and class balance/data scale.
7. Record parameters, random seeds, software versions, runtimes, and output
   paths so the experiment can be repeated.
8. Interpret model outputs in relation to the research question; do not claim
   causality from observational patterns.

## Task-specific checks

- Clustering: scale numeric features as appropriate, compare cluster counts,
  report silhouette or another justified measure, and profile the clusters.
- Rating prediction: use only information available at prediction time; report
  RMSE/MAE and compare against global- and movie-average baselines.
- Tags and genome: measure coverage and treat missingness as unknown, not as
  zero preference or zero relevance.
- External metadata: verify provider terms and temporal alignment before using
  it as a mining feature.
