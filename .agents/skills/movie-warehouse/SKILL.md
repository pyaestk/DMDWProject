---
name: movie-warehouse
description: Design, build, or review the MovieLens project staging and data warehouse, including source integration, dimensional modeling, ETL checks, and OLAP.
---

# Movie warehouse workflow

Use this skill for data-source integration, staging, ETL, star/snowflake schema,
data quality, and OLAP work in this repository.

## Steps

1. Read `AGENTS.md`, the active backlog task, and the relevant source terms.
2. Inventory source schemas and sample records. Do not mutate raw files.
3. Write a source register with publisher, version/retrieval date, license,
   primary key, crosswalk key, and planned target fields.
4. Measure cross-source identifier match rate on a bounded pilot before
   downloading or transforming the full source.
5. Document each table's grain and define facts, dimensions, surrogate keys,
   degenerate dimensions, and any SCD behavior.
6. Stage raw-to-clean mappings explicitly; define missing-value, duplicate,
   anomaly, and unmatched-record handling.
7. Load reproducibly and validate counts, uniqueness, referential integrity,
   null rates, and match rates.
8. Implement OLAP questions with clear slice/dice, roll-up, drill-down, pivot,
   and aggregation behavior where applicable.
9. Record measured query times only after executing them on the stated setup.

## Important modeling rules

- Treat MovieLens as one source even though it contains six files.
- Keep rating, tag-application, and genome-score grains separate.
- Aggregate before joining any one-to-many enrichment that could duplicate
  rating facts.
- Never discard unmatched source records silently; preserve them and report the
  match coverage.
