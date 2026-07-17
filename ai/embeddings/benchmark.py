#!/usr/bin/env python3
"""
Benchmark embedding retrieval quality and speed.

Usage:
    python ai/embeddings/benchmark.py --queries 50 --top-k 10
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

BENCHMARK_QUERIES = [
    "fundamental rights Indian Constitution",
    "Article 21 personal liberty",
    "doctrine of basic structure",
    "preventive detention habeas corpus",
    "right to equality Article 14",
    "freedom of speech Article 19",
    "judicial review constitutional amendment",
    "Directive Principles of State Policy",
    "writ jurisdiction High Court Supreme Court",
    "natural justice audi alteram partem",
]


async def run_benchmark(num_queries: int, top_k: int) -> None:
    from app.services.ai.embedding_service import EmbeddingService

    embedder = EmbeddingService()
    queries = (BENCHMARK_QUERIES * (num_queries // len(BENCHMARK_QUERIES) + 1))[:num_queries]

    print(f"Running {len(queries)} retrieval queries (top_k={top_k})...")

    latencies = []
    for i, q in enumerate(queries, 1):
        start = time.perf_counter()
        results = await embedder.similarity_search(q, n_results=top_k)
        ms = (time.perf_counter() - start) * 1000
        latencies.append(ms)
        count = len(results.get("documents", [[]])[0])
        print(f"  [{i:3d}] {ms:6.1f}ms  {count} results  — {q[:50]}")

    avg = sum(latencies) / len(latencies)
    p50 = sorted(latencies)[len(latencies) // 2]
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    p99 = sorted(latencies)[int(len(latencies) * 0.99)]

    print(f"\n{'='*50}")
    print(f"Avg latency : {avg:.1f}ms")
    print(f"P50 latency : {p50:.1f}ms")
    print(f"P95 latency : {p95:.1f}ms")
    print(f"P99 latency : {p99:.1f}ms")
    print(f"Min/Max     : {min(latencies):.1f}ms / {max(latencies):.1f}ms")

    collection_count = await embedder.get_collection_count()
    print(f"Collection  : {collection_count:,} vectors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.queries, args.top_k))
