#!/usr/bin/env python3
"""
Download the ChronoLegal dataset from HuggingFace.

Usage:
    python scripts/data/01_download_dataset.py --output /data/chronolegal

The ChronoLegal dataset contains thousands of Indian legal judgments
with structured metadata.
"""
import argparse
import sys
from pathlib import Path


def download(output_dir: str) -> None:
    try:
        from datasets import load_dataset
    except ImportError:
        print("Run: pip install datasets")
        sys.exit(1)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("Downloading ChronoLegal dataset from HuggingFace...")
    try:
        # Primary: ChronoLegal
        dataset = load_dataset(
            "rceborg/ChronoLegal",
            trust_remote_code=True,
        )
        print(f"Dataset loaded: {dataset}")
        dataset.save_to_disk(str(out / "raw"))
        print(f"Saved to {out / 'raw'}")
    except Exception as e:
        print(f"ChronoLegal not found ({e}), trying alternative...")
        try:
            # Fallback: Indian Legal Dataset
            dataset = load_dataset("Legal-AI/Indian-Legal-Dataset", trust_remote_code=True)
            dataset.save_to_disk(str(out / "raw"))
            print(f"Fallback dataset saved to {out / 'raw'}")
        except Exception as e2:
            print(f"Both downloads failed: {e2}")
            print("Please manually place legal judgment JSON files in:", out)
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/data/chronolegal")
    args = parser.parse_args()
    download(args.output)
