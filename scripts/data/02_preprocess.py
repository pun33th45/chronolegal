#!/usr/bin/env python3
"""
Preprocess and normalize the ChronoLegal dataset.
Cleans text, normalizes fields, extracts metadata, writes JSONL.

Usage:
    python scripts/data/02_preprocess.py \
        --input /data/chronolegal/raw \
        --output /data/processed/cases.jsonl
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    return text.strip()


def parse_date(date_str: str) -> str | None:
    if not date_str:
        return None
    formats = [
        "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y",
        "%B %d, %Y", "%d %B %Y", "%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize_case(raw: dict) -> dict:
    """Normalize a raw case record into our schema."""
    case_id = str(raw.get("id", raw.get("case_id", "")))
    if not case_id:
        return {}

    return {
        "case_id": case_id,
        "case_name": clean_text(raw.get("case_name", raw.get("title", ""))),
        "case_number": clean_text(raw.get("case_number", "")),
        "petitioner": clean_text(raw.get("petitioner", raw.get("appellant", ""))),
        "respondent": clean_text(raw.get("respondent", "")),
        "court": clean_text(raw.get("court", raw.get("court_name", ""))),
        "bench": clean_text(raw.get("bench", "")),
        "judges": [
            clean_text(j)
            for j in (raw.get("judges", raw.get("judge", [])) or [])
            if j
        ],
        "judgment_date": parse_date(
            str(raw.get("date", raw.get("judgment_date", raw.get("decision_date", ""))))
        ),
        "acts": [clean_text(a) for a in (raw.get("acts", []) or []) if a],
        "sections": [clean_text(s) for s in (raw.get("sections", []) or []) if s],
        "keywords": [clean_text(k) for k in (raw.get("keywords", []) or []) if k],
        "full_text": clean_text(raw.get("judgment", raw.get("full_text", raw.get("text", "")))),
        "summary": clean_text(raw.get("summary", raw.get("headnotes", ""))),
        "headnotes": clean_text(raw.get("headnotes", "")),
        "decision_type": clean_text(raw.get("decision_type", raw.get("outcome_type", ""))),
        "outcome": clean_text(raw.get("outcome", "")),
        "cited_cases": [
            clean_text(c) for c in (raw.get("cited_cases", raw.get("citations", [])) or []) if c
        ],
        "source_url": raw.get("url", raw.get("source_url", "")),
    }


def process(input_path: str, output_path: str) -> None:
    inp = Path(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    skipped = 0

    with open(out, "w", encoding="utf-8") as f_out:
        # Handle HuggingFace dataset format
        if (inp / "dataset_info.json").exists():
            try:
                from datasets import load_from_disk
                ds = load_from_disk(str(inp))
                split = ds.get("train", list(ds.values())[0])
                for item in split:
                    normalized = normalize_case(dict(item))
                    if normalized.get("case_name"):
                        f_out.write(json.dumps(normalized, ensure_ascii=False) + "\n")
                        count += 1
                    else:
                        skipped += 1
                print(f"Processed {count} cases ({skipped} skipped) → {out}")
                return
            except Exception as e:
                print(f"HuggingFace format load failed: {e}, trying JSON files...")

        # Handle raw JSON files
        json_files = list(inp.glob("**/*.json")) + list(inp.glob("**/*.jsonl"))
        for jf in json_files:
            with open(jf, encoding="utf-8") as f:
                try:
                    if jf.suffix == ".jsonl":
                        for line in f:
                            raw = json.loads(line)
                            normalized = normalize_case(raw)
                            if normalized.get("case_name"):
                                f_out.write(json.dumps(normalized, ensure_ascii=False) + "\n")
                                count += 1
                            else:
                                skipped += 1
                    else:
                        data = json.load(f)
                        items = data if isinstance(data, list) else [data]
                        for raw in items:
                            normalized = normalize_case(raw)
                            if normalized.get("case_name"):
                                f_out.write(json.dumps(normalized, ensure_ascii=False) + "\n")
                                count += 1
                            else:
                                skipped += 1
                except json.JSONDecodeError as e:
                    print(f"Skipping {jf}: {e}")

    print(f"Processed {count} cases ({skipped} skipped) → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/data/chronolegal/raw")
    parser.add_argument("--output", default="/data/processed/cases.jsonl")
    args = parser.parse_args()
    process(args.input, args.output)
