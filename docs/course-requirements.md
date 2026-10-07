# ITCS544 project requirements summary

This summary is based on `2026T1_L03p_ITCS544_Project.pdf` supplied by the
team. Check the original brief if any item is ambiguous.

## Core technical requirements

- Raw dataset scale: at least 5 million records.
- Multi-tier data warehouse: Staging → Enterprise DW / Data Marts.
- Dimensional model: star schema, snowflake schema, or Data Vault 2.0; define
  facts, dimensions, SCD Type 2 or 3, and degenerate dimensions.
- Automated ETL/ELT: extraction, schema validation, anomaly detection,
  deduplication, missing-value imputation, and surrogate-key generation.
- OLAP: support cube, roll-up, drill-down, pivot, and slice/dice analysis.
- Data mining: at least two distinct categories from classification/regression,
  clustering/density estimation, pattern/association mining, or anomaly
  detection.
- Evaluation: use suitable baselines and metrics, including applicable metrics
  such as ROC-AUC, precision-recall, silhouette score, and runtime/throughput.

## Deliverables and dates

| Deliverable | Due date | Main expectations |
| --- | --- | --- |
| Proposal | 2026-09-01 | Problem and hypotheses, data audit, architecture, team work plan; PDF up to 4 pages |
| Progress report | 2026-10-13 | Functional warehouse and ETL, ERD, quality metrics, five timed OLAP queries, preliminary mining pipeline; PDF up to 8 pages and live demo |
| Presentation | 2026-11-17 | 10-minute technical presentation, architecture defense, and live demo |
| Final report and repository | 2026-11-30 | 10–14 page report, operational mining results, benchmarks, reproducible documented code repository |

The assignment brief is a requirements source. Team-specific decisions and any
instructor clarifications should be recorded separately under
`docs/decisions/`.
