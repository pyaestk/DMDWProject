# TASK-003: Build the warehouse and OLAP progress-report baseline

**Status:** Done  
**Owner:** Team  
**Course milestone:** Progress report  
**Target date:** 2026-10-13

## Goal

Deliver an implemented, validated warehouse and repeatable ETL foundation for
the ITCS544 progress report and live demonstration.

## Dependencies

- TASK-002: Select and validate an independent movie metadata source.

Wikidata is selected as the secondary source. The full match frame has now
been audited; see `docs/decisions/2026-09-28-wikidata-secondary-source.md` and
`docs/source-register.md`. Reconcile this audit again if the source snapshot,
IMDb normalization, or matching rules change during ETL.

## Scope

- Produce logical/physical models, ERD, bus matrix, fact/dimension definitions,
  and documented table grains.
- Implement staging and an automated, repeatable ETL/ELT path with schema,
  quality, duplicate, missing-value, and key checks.
- Implement the required SCD Type 2 or Type 3 behavior and identify any
  degenerate dimensions that fit the design.
- Populate the warehouse and implement five multi-dimensional OLAP queries.
- Measure query times and explain the actual indexing/partitioning choices.
- Record quality metrics before and after transformations.

## Acceptance criteria

- [x] Warehouse has traceable mappings from both approved sources.
- [x] Warehouse row counts, keys, and referential-integrity checks are recorded.
- [x] ERD, bus matrix, schema, SCD behavior, and fact grains are documented.
- [x] ETL can be rerun from documented source files and parameters.
- [x] Five OLAP queries execute and their runtimes are measured on a documented
      environment.
- [x] Progress-report evidence matches what was implemented and executed.

## Verification plan

- Reconcile staging, warehouse, and source counts.
- Execute the ETL from a clean derived-output state.
- Time all five OLAP queries using the same documented method.

## Completion notes

- Changed files/artifacts: ETL implementation and schemas; warehouse and ETL
  evidence; `notebooks/olap_analysis.ipynb`; `outputs/olap/olap_run.json`;
  `docs/olap-results.md`; and updates to `docs/warehouse-design.md`,
  `README.md`, and this task record.
- Verification actually performed: completed the full source-to-warehouse load;
  reconciled staged and fact counts; checked validation/rejection counts,
  dimension coverage, and all foreign keys. The run recorded zero foreign-key
  violations.
- Results and limitations: 20,000,263 ratings loaded; 465,557 tag events loaded
  after rejecting seven blank tag rows; 11,709,768 genome scores loaded. Type 2
  incremental behavior is implemented but only one metadata snapshot has been
  loaded. The five OLAP queries are now implemented and timed; see
  `notebooks/olap_analysis.ipynb` and `docs/olap-results.md`.

## Work started on 2026-09-28

- Confirmed the six local MovieLens CSVs remain one source; Wikidata is the
  independent metadata source.
- Began with the logical/physical model and source-to-target grains before
  implementing ETL. See `docs/warehouse-design.md` and `sql/`.
- Drafted the bus matrix, relationship sketch, Type 2 policy, lineage-key
  design, and initial OLAP questions. The SQL schema is now executed and loaded
  through the documented ETL.
- Completed the full Wikidata lookup for all 27,278 MovieLens `links.csv` rows
  with nonzero IMDb IDs: 26,263 matched (96.28%), 981 unmatched, and 34
  ambiguous. Field coverage and the one shared QID are documented in the
  source register; raw result is in
  `outputs/source_audit/wikidata_match_full_catalog_2026-09-28.json`.
- Extended `tools/wikidata_match_pilot.py` with full-catalog mode and a
  resumable JSONL checkpoint. The API throttled an initial run and rejected
  batches of 100 as too complex; the completed run resumed with 50-title
  batches and a five-second pause.
- Implemented `tools/build_warehouse.py`, staging DDL, ETL audit tables, and
  the language dimension/bridge. First load completed successfully; see
  `docs/etl-runbook.md` and `outputs/etl/etl_run_1_20260928T150023Z.json`.
- First-load counts: 20,000,263 ratings; 465,557 accepted user-tag events
  (seven blank tags rejected but preserved in staging); 11,709,768 genome
  scores; 27,278 current movie rows; 138,493 users; and 26,263 exact Wikidata
  enrichments. Foreign-key violations: zero.
- Type 2 logic is implemented for changed movie attributes on incremental
  loads. Only the initial snapshot has been loaded, so no historical Type 2
  change has yet been observed.
- Implemented and executed the five OLAP analyses in
  `notebooks/olap_analysis.ipynb`. The full queries returned 4,792, 20, 40,
  324,427, and 590 aggregate rows, respectively; elapsed times were 162.935,
  25.890, 81.855, 2.268, and 134.937 seconds. The companion Wikidata coverage
  summary took 0.799 seconds. See `docs/olap-results.md` for the environment,
  measurement method, caveats, and index-plan findings.
- Notebook code cells ran sequentially in one Python process because the
  sandbox blocked a normal Jupyter kernel's local connection. The warehouse
  was opened read-only; the saved notebook includes its executed code and
  outputs and remains rerunnable with a regular Jupyter kernel.
