#!/usr/bin/env python3
"""Measure MovieLens-to-Wikidata IMDb-ID coverage with resumable checkpoints."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "ml-20m" / "links.csv"
DEFAULT_BATCH_SIZE = 50
API_URL = "https://www.wikidata.org/w/api.php?action=wbgraphql&format=json"
USER_AGENT = "ITCS544MoviePreferenceProject/1.0 (academic movie metadata coverage audit)"


def imdb_identifier(raw_id: str) -> str:
    """Convert MovieLens's numeric IMDb ID to the Wikidata P345 form."""
    return "tt" + raw_id.strip().zfill(7)


def query_field(alias: str, imdb_id: str) -> str:
    return f'''{alias}: itemByExternalId(property: "P345", externalId: "{imdb_id}") {{
      ... on Item {{
        id
        label(languageCode: "en")
        releaseDate: statements(propertyId: "P577") {{ value {{ ... on TimeValue {{ time }} }} }}
        originalLanguage: statements(propertyId: "P364") {{ value {{ ... on ItemValue {{ id label(languageCode: "en") }} }} }}
        director: statements(propertyId: "P57") {{ value {{ ... on ItemValue {{ id label(languageCode: "en") }} }} }}
        runtime: statements(propertyId: "P2047") {{ value {{ ... on QuantityValue {{ amount }} }} }}
        country: statements(propertyId: "P495") {{ value {{ ... on ItemValue {{ id label(languageCode: "en") }} }} }}
        genre: statements(propertyId: "P136") {{ value {{ ... on ItemValue {{ id label(languageCode: "en") }} }} }}
      }}
      ... on ExternalIdNonUnique {{ items }}
    }}'''


def fetch_batch(batch: list[dict[str, str]], offset: int) -> dict:
    fields = [
        query_field(f"m{offset + index}", imdb_identifier(row["imdbId"]))
        for index, row in enumerate(batch)
    ]
    query = "query MovieMatchPilot {\n" + "\n".join(fields) + "\n}"
    body = json.dumps({"query": query}).encode("utf-8")
    request = Request(
        API_URL,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            result = json.load(response)
    except HTTPError as error:
        if error.code == 429:
            retry_after = error.headers.get("Retry-After", "not provided")
            raise RuntimeError(
                "Wikidata returned HTTP 429; Retry-After is "
                f"{retry_after}. Stop and resume after the stated cooldown."
            ) from error
        raise RuntimeError(f"Wikidata request failed with HTTP {error.code}.") from error
    except (TimeoutError, URLError) as error:
        raise RuntimeError(f"Wikidata request failed: {error}") from error

    if result.get("errors"):
        raise RuntimeError("Wikidata GraphQL error: " + json.dumps(result["errors"]))
    return result["data"]


def payload_values(container: list[dict] | None) -> list[dict]:
    return [entry["value"] for entry in (container or []) if entry.get("value")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=544)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--delay-seconds", type=float, default=5.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--full-catalog",
        action="store_true",
        help="audit every links.csv row with a nonzero IMDb ID instead of sampling",
    )
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="continue from the JSONL checkpoint created by an earlier run",
    )
    args = parser.parse_args()

    if args.sample_size <= 0 or args.batch_size <= 0 or args.delay_seconds < 0:
        parser.error("--sample-size and --batch-size must be positive; delay cannot be negative")
    with args.input.open(newline="", encoding="utf-8") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if row.get("imdbId") and row["imdbId"].strip() not in {"", "0"}
        ]
    if not rows:
        raise RuntimeError(f"No usable IMDb IDs were found in {args.input}.")

    selected_rows = (
        rows
        if args.full_catalog
        else random.Random(args.seed).sample(rows, min(args.sample_size, len(rows)))
    )
    default_name = "wikidata_match_full_catalog" if args.full_catalog else "wikidata_match_pilot"
    output = args.output or ROOT / "outputs" / "source_audit" / f"{default_name}_{date.today().isoformat()}.json"
    checkpoint = args.checkpoint or output.with_suffix(output.suffix + ".jsonl")
    input_label = str(args.input.relative_to(ROOT)) if args.input.is_relative_to(ROOT) else str(args.input)
    frame_digest = hashlib.sha256(
        "\n".join(f"{row['movieId']}:{row['imdbId']}" for row in selected_rows).encode("utf-8")
    ).hexdigest()
    manifest = {
        "input": input_label,
        "selection": "full_catalog" if args.full_catalog else "deterministic_sample",
        "selectedCount": len(selected_rows),
        "randomSeed": None if args.full_catalog else args.seed,
        "frameSha256": frame_digest,
    }

    completed: dict[str, dict] = {}
    if checkpoint.exists():
        if not args.resume:
            raise RuntimeError(
                f"Checkpoint already exists at {checkpoint}; pass --resume to continue "
                "or choose a new --checkpoint path."
            )
        with checkpoint.open(encoding="utf-8") as stream:
            first_line = stream.readline()
            try:
                checkpoint_manifest = json.loads(first_line)
            except json.JSONDecodeError as error:
                raise RuntimeError(f"Invalid checkpoint header in {checkpoint}.") from error
            saved_manifest = checkpoint_manifest.get("_manifest", {})
            if saved_manifest != manifest and {
                key: value for key, value in saved_manifest.items() if key != "batchSize"
            } != manifest:
                raise RuntimeError(
                    "Checkpoint settings or source frame differ from this run; "
                    "choose the matching input/options or a new checkpoint."
                )
            for line_number, line in enumerate(stream, start=2):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    raise RuntimeError(
                        f"Invalid checkpoint record on line {line_number}."
                    ) from error
                completed[record["movieId"]] = record
    else:
        if args.resume:
            raise RuntimeError(f"No checkpoint exists at {checkpoint} to resume.")
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        with checkpoint.open("w", encoding="utf-8") as stream:
            stream.write(json.dumps({"_manifest": manifest}) + "\n")

    pending_rows = [row for row in selected_rows if row["movieId"] not in completed]
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint.open("a", encoding="utf-8") as checkpoint_stream:
        for start in range(0, len(pending_rows), args.batch_size):
            batch = pending_rows[start : start + args.batch_size]
            data = fetch_batch(batch, 0)
            for index, row in enumerate(batch):
                alias = f"m{index}"
                wikidata = data.get(alias)
                common = {
                    "movieId": row["movieId"],
                    "imdbId": imdb_identifier(row["imdbId"]),
                }
                if wikidata is None:
                    record = {**common, "wikidataQid": None, "matchStatus": "unmatched"}
                elif "items" in wikidata:
                    record = {
                        **common,
                        "wikidataQid": wikidata["items"],
                        "matchStatus": "ambiguous",
                    }
                else:
                    record = {
                        **common,
                        "wikidataQid": wikidata.get("id"),
                        "matchStatus": "matched",
                        "wikidataTitle": wikidata.get("label"),
                        "releaseDates": payload_values(wikidata.get("releaseDate")),
                        "languages": payload_values(wikidata.get("originalLanguage")),
                        "directors": payload_values(wikidata.get("director")),
                        "runtimes": payload_values(wikidata.get("runtime")),
                        "countries": payload_values(wikidata.get("country")),
                        "genres": payload_values(wikidata.get("genre")),
                    }
                completed[row["movieId"]] = record
                checkpoint_stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            checkpoint_stream.flush()
            done = len(completed)
            print(f"Wikidata audit progress: {done}/{len(selected_rows)} titles", flush=True)
            if start + args.batch_size < len(pending_rows):
                time.sleep(args.delay_seconds)

    matches = [completed[row["movieId"]] for row in selected_rows]
    matched = [record for record in matches if record["matchStatus"] == "matched"]
    qid_counts = Counter(record["wikidataQid"] for record in matched)
    duplicate_qids = {qid: count for qid, count in qid_counts.items() if count > 1}
    attribute_counts = {
        field: sum(bool(record.get(field)) for record in matched)
        for field in ("releaseDates", "languages", "directors", "runtimes", "countries", "genres")
    }
    summary = {
        "source": "Wikidata",
        "retrievedOn": date.today().isoformat(),
        "method": "Wikibase GraphQL itemByExternalId with P345 IMDb identifier",
        "input": input_label,
        "sourceFrame": "MovieLens links.csv rows with nonzero imdbId",
        "fullCatalog": args.full_catalog,
        "randomSeed": None if args.full_catalog else args.seed,
        "selectedTitleCount": len(selected_rows),
        "matched": len(matched),
        "unmatched": sum(record["matchStatus"] == "unmatched" for record in matches),
        "ambiguous": sum(record["matchStatus"] == "ambiguous" for record in matches),
        "matchRate": round(len(matched) / len(selected_rows), 4),
        "uniqueWikidataQids": len(qid_counts),
        "duplicateQidCount": len(duplicate_qids),
        "matchedMoviesOnDuplicateQids": sum(duplicate_qids.values()),
        "attributeCoverageAmongMatched": attribute_counts,
        "attributeCoverageRateAmongMatched": {
            field: round(count / len(matched), 4) if matched else 0
            for field, count in attribute_counts.items()
        },
    }
    result = {"summary": summary, "matches": matches}

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved audit results to {output.relative_to(ROOT) if output.is_relative_to(ROOT) else output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
