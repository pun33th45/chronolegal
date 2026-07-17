#!/usr/bin/env python3
"""
Standalone indexing pipeline — watch a directory and embed new files.

Usage:
    python ai/pipeline/indexer.py --watch /data/incoming --interval 60
"""
import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))


async def process_file(filepath: Path) -> None:
    from app.services.ai.document_processor import DocumentProcessor

    processor = DocumentProcessor()
    content = filepath.read_bytes()
    suffix = filepath.suffix.lower()

    content_type_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".txt": "text/plain",
        ".json": "application/json",
    }
    content_type = content_type_map.get(suffix, "text/plain")

    task_id = await processor.process_upload(
        content=content,
        filename=filepath.name,
        content_type=content_type,
        user_id="system_indexer",
    )
    print(f"  → Task {task_id}: {filepath.name}")


async def watch_directory(watch_dir: str, interval: int, processed_log: str) -> None:
    watch_path = Path(watch_dir)
    watch_path.mkdir(parents=True, exist_ok=True)
    log_path = Path(processed_log)

    processed: set[str] = set()
    if log_path.exists():
        with open(log_path) as f:
            processed = set(json.load(f))

    print(f"Watching {watch_path} every {interval}s...")

    while True:
        files = list(watch_path.glob("**/*"))
        new_files = [
            f for f in files
            if f.is_file()
            and f.suffix.lower() in {".pdf", ".docx", ".doc", ".txt", ".json"}
            and hashlib.md5(str(f).encode()).hexdigest() not in processed
        ]

        if new_files:
            print(f"Found {len(new_files)} new file(s)")
            for filepath in new_files:
                try:
                    await process_file(filepath)
                    processed.add(hashlib.md5(str(filepath).encode()).hexdigest())
                except Exception as e:
                    print(f"  Error processing {filepath.name}: {e}")

            with open(log_path, "w") as f:
                json.dump(list(processed), f)

        await asyncio.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", default="/data/incoming")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--processed-log", default="/data/processed/.indexed.json")
    args = parser.parse_args()
    asyncio.run(watch_directory(args.watch, args.interval, args.processed_log))
