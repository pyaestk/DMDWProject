# Derived data

Keep generated staging and warehouse files here, separated from original
sources in `ml-20m/`. Document each generated dataset's inputs, schema, run
parameters, and creation command. Do not commit large generated data unless the
team has agreed to do so.

The ETL creates `warehouse/movie_preference.sqlite`, containing the `stg_*`
source tables and dimensional warehouse. The first successful load produced a
database of about 5.7 GB. Rebuild instructions and ETL evidence are in
`../docs/etl-runbook.md` and `../outputs/etl/`.
