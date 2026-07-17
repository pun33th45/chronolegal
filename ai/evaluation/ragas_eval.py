#!/usr/bin/env python3
"""
ChronoLegal RAG Evaluation Suite

Metrics:
  - Exact Match (EM)     : Does answer contain key ground-truth phrases?
  - F1 Score             : Token overlap between answer and ground truth
  - Precision / Recall   : Token-level precision and recall
  - MRR                  : Mean Reciprocal Rank of expected cases in citations
  - nDCG                 : Normalised Discounted Cumulative Gain of citations
  - Faithfulness         : Fraction of answer claims grounded in retrieved context
  - Hallucination Rate   : 1 - faithfulness
  - Latency              : End-to-end response time in milliseconds

Usage:
    python ai/evaluation/ragas_eval.py \
        --questions ai/evaluation/eval_questions.json \
        --output ai/evaluation/results.json \
        --top-k 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    return set(text.lower().split())


def token_precision_recall_f1(answer: str, ground_truth: str) -> tuple[float, float, float]:
    if not ground_truth:
        return 0.0, 0.0, 0.0
    a_tok = _tokenize(answer)
    g_tok = _tokenize(ground_truth)
    if not a_tok:
        return 0.0, 0.0, 0.0
    precision = len(a_tok & g_tok) / len(a_tok)
    recall = len(a_tok & g_tok) / len(g_tok) if g_tok else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


def exact_match(answer: str, ground_truth: str, threshold: float = 0.6) -> float:
    """
    Soft exact match: fraction of ground-truth key phrases (4+ char tokens)
    found in the answer. Returns 1.0 if >= threshold fraction present.
    """
    if not ground_truth:
        return 0.0
    key_tokens = [t for t in ground_truth.lower().split() if len(t) >= 4]
    if not key_tokens:
        return 0.0
    answer_lower = answer.lower()
    matched = sum(1 for t in key_tokens if t in answer_lower)
    score = matched / len(key_tokens)
    return round(score, 4)


def reciprocal_rank(citations: list[Any], expected_cases: list[str]) -> float:
    """MRR contribution for one query: 1/rank of first relevant citation."""
    if not expected_cases:
        return 1.0  # no expectation — not penalised
    for rank, citation in enumerate(citations, 1):
        name = getattr(citation, "case_name", "") or ""
        if any(exp.lower() in name.lower() or name.lower() in exp.lower()
               for exp in expected_cases):
            return 1.0 / rank
    return 0.0


def ndcg(citations: list[Any], expected_cases: list[str], k: int = 5) -> float:
    """nDCG@k: relevance = 1 if citation matches an expected case, else 0."""
    if not expected_cases:
        return 1.0
    cits = citations[:k]
    relevances = []
    for c in cits:
        name = getattr(c, "case_name", "") or ""
        rel = 1 if any(exp.lower() in name.lower() or name.lower() in exp.lower()
                       for exp in expected_cases) else 0
        relevances.append(rel)

    dcg = sum(r / math.log2(i + 2) for i, r in enumerate(relevances))
    ideal_rels = sorted(relevances, reverse=True)
    idcg = sum(r / math.log2(i + 2) for i, r in enumerate(ideal_rels))
    return round(dcg / idcg, 4) if idcg else 0.0


def faithfulness_score(answer: str, context_text: str) -> tuple[float, float]:
    """
    Faithfulness: fraction of non-trivial answer sentences supported by context.
    Hallucination rate = 1 - faithfulness.
    """
    sentences = [s.strip() for s in answer.split(".") if len(s.strip()) > 15]
    if not sentences:
        return 1.0, 0.0
    ctx_lower = context_text.lower()
    supported = 0
    for sentence in sentences:
        words = [w for w in sentence.lower().split() if len(w) >= 5][:5]
        if words and sum(1 for w in words if w in ctx_lower) / len(words) >= 0.4:
            supported += 1
    faith = round(supported / len(sentences), 4)
    halluc = round(1.0 - faith, 4)
    return faith, halluc


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

async def evaluate(questions_path: str, output_path: str, top_k: int = 5) -> None:
    from app.services.ai.rag_pipeline import RAGPipeline

    with open(questions_path, encoding="utf-8") as f:
        eval_set: list[dict] = json.load(f)

    pipeline = RAGPipeline()
    results = []

    print(f"\nChronoLegal RAG Evaluation — {len(eval_set)} questions | top_k={top_k}")
    print("=" * 70)

    for i, item in enumerate(eval_set, 1):
        question = item["question"]
        ground_truth = item.get("ground_truth", "")
        expected_cases = item.get("expected_cases", [])

        start = time.perf_counter()
        result = await pipeline.run(query=question, top_k=top_k)
        latency_ms = int((time.perf_counter() - start) * 1000)

        precision, recall, f1 = token_precision_recall_f1(result.answer, ground_truth)
        em = exact_match(result.answer, ground_truth)
        rr = reciprocal_rank(result.citations, expected_cases)
        ndcg_score = ndcg(result.citations, expected_cases, k=top_k)

        context_text = " ".join(
            getattr(c, "content", getattr(c, "chunk_text", ""))
            for c in result.citations
        )
        faith, halluc = faithfulness_score(result.answer, context_text)

        top_score = result.citations[0].similarity_score if result.citations else 0.0

        entry = {
            "question": question,
            "answer": result.answer[:500] + "..." if len(result.answer) > 500 else result.answer,
            "ground_truth": ground_truth,
            "expected_cases": expected_cases,
            "citations_returned": [
                getattr(c, "case_name", "") for c in result.citations
            ],
            "sufficient_context": result.sufficient_context,
            "latency_ms": latency_ms,
            "metrics": {
                "exact_match": em,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "mrr": rr,
                "ndcg": ndcg_score,
                "faithfulness": faith,
                "hallucination_rate": halluc,
                "top_citation_score": round(top_score, 4),
            },
        }
        results.append(entry)

        print(
            f"  [{i:2d}/{len(eval_set)}] "
            f"EM={em:.2f} F1={f1:.2f} MRR={rr:.2f} "
            f"Faith={faith:.2f} Halluc={halluc:.2f} {latency_ms}ms"
        )

    # ------------------------------------------------------------------
    # Aggregate metrics
    # ------------------------------------------------------------------
    n = len(results)

    def avg(key: str) -> float:
        return round(sum(r["metrics"][key] for r in results) / n, 4)

    summary = {
        "evaluation_config": {
            "total_questions": n,
            "top_k": top_k,
        },
        "aggregate_metrics": {
            "exact_match": avg("exact_match"),
            "precision": avg("precision"),
            "recall": avg("recall"),
            "f1": avg("f1"),
            "mrr": avg("mrr"),
            "ndcg": avg("ndcg"),
            "faithfulness": avg("faithfulness"),
            "hallucination_rate": avg("hallucination_rate"),
            "avg_latency_ms": round(sum(r["latency_ms"] for r in results) / n, 1),
            "sufficient_context_pct": round(
                sum(1 for r in results if r["sufficient_context"]) / n * 100, 1
            ),
        },
        "results": results,
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    m = summary["aggregate_metrics"]
    print(f"\n{'=' * 70}")
    print(f"  Exact Match       : {m['exact_match']:.4f}")
    print(f"  Precision         : {m['precision']:.4f}")
    print(f"  Recall            : {m['recall']:.4f}")
    print(f"  F1 Score          : {m['f1']:.4f}")
    print(f"  MRR               : {m['mrr']:.4f}")
    print(f"  nDCG@{top_k}           : {m['ndcg']:.4f}")
    print(f"  Faithfulness      : {m['faithfulness']:.4f}")
    print(f"  Hallucination Rate: {m['hallucination_rate']:.4f}")
    print(f"  Avg Latency       : {m['avg_latency_ms']:.0f}ms")
    print(f"  Sufficient Ctx    : {m['sufficient_context_pct']:.1f}%")
    print(f"\n  Results saved → {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate ChronoLegal RAG pipeline")
    parser.add_argument("--questions", default="ai/evaluation/eval_questions.json")
    parser.add_argument("--output", default="ai/evaluation/results.json")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(evaluate(args.questions, args.output, args.top_k))
