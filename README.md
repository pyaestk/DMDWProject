# Movie Preference Analysis — ITCS544

This repository is the team workspace for designing a data warehouse and data
mining workflow around MovieLens 20M. `docs/course-requirements.md` summarizes
the course brief; `AGENTS.md` explains how AI-assisted work should use those
requirements and the team's decisions.

## Getting started for teammates

After cloning or downloading this repository:

1. Install Python 3 if it is not already available. The warehouse builder uses
   Python's standard library and SQLite, so it needs no extra Python packages.
2. Download [MovieLens 20M from GroupLens](https://grouplens.org/datasets/movielens/20m/)
   and extract it into `ml-20m/` directly inside the project folder. The CSVs
   should be at paths such as `ml-20m/ratings.csv`, not
   `ml-20m/ml-20m/ratings.csv`. Keep all six original CSV files unchanged.
3. Confirm the repository includes the required Wikidata audit:
   `outputs/source_audit/wikidata_match_full_catalog_2026-09-28.json`.
4. Open a terminal in the project folder (the folder containing this README)
   and build your local warehouse:

   ```bash
   python3 tools/build_warehouse.py
   ```

This creates `data/warehouse/movie_preference.sqlite` and an ETL evidence
report under `outputs/etl/`. The raw MovieLens files and generated warehouse
are excluded from Git, so each teammate needs to download the source data and
build the warehouse locally.

Follow the [ETL runbook](docs/etl-runbook.md) for input details, verification
evidence, and instructions for rebuilding an existing database. Once the
warehouse is ready, start with [the OLAP notebook](notebooks/olap_analysis.ipynb)
or [the preliminary mining notebook](notebooks/mining_preliminary.ipynb).

## Current contents

- `ml-20m/`: original MovieLens 20M files. Treat as read-only source data.
- `.codex/agents/`: role playbooks for warehouse/ETL, mining, and review work.
- `.agents/skills/`: reusable project workflows for warehouse and mining tasks.
- `backlog/`: scoped tasks, drafts, completed work, and task templates.
- `docs/`: architecture, data dictionary, decisions, and reproducibility notes.
- `sql/`: staging and physical warehouse schemas.
- `tools/build_warehouse.py`: repeatable SQLite staging and warehouse ETL.
- `tools/`: bounded source-audit and project utility scripts.
- `data/`: derived staging and warehouse data; never store secrets here.
- `notebooks/`: runnable OLAP and preliminary mining analyses.
- `outputs/`: generated analysis and model outputs.
- `reports/`: proposal, progress, and final report working files.

Create generated folders only when the first relevant task needs them. Keep raw
source data out of generated-output folders.

## How to use the project support

1. Start with `AGENTS.md` and create or select a task in `backlog/tasks/`.
2. Read the relevant agent playbook and project skill.
3. Implement only the task's agreed scope, preserving the raw data.
4. Record row counts, data quality checks, and evidence in the task or report.
5. Update acceptance criteria and move completed tasks to `backlog/completed/`.

The playbooks and skills guide AI-assisted work; they do not launch agents or
run a backlog application automatically.

## Current project decisions

Record approved sources, identifiers, licensing, modeling grain, mining scope,
and evaluation choices in `docs/decisions/`. The agreed mining scope includes
both H2 clustering and H3 rating prediction. Keep data-source selection and
source-use approval documented separately.

The warehouse model is in `docs/warehouse-design.md`; DDL is in `sql/`. The
first ETL load, full Wikidata coverage audit, and five OLAP analyses are
complete. See `docs/etl-runbook.md` for rebuild instructions,
`notebooks/olap_analysis.ipynb` to rerun the analyses, and
`docs/olap-results.md` for measured runtimes and query-plan notes. Preliminary
EDA, H2 clustering, H3 baselines, and a progress-report draft are in
`notebooks/mining_preliminary.ipynb`, `docs/mining-preliminary-results.md`,
and `reports/progress-report-draft.md`.
