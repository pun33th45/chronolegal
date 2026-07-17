#!/usr/bin/env python3
"""
ChronoLegal RAG Evaluation Suite

Metrics:
  - Exact Match (EM)     : Soft key-phrase match between answer and ground truth
  - F1 Score             : Token overlap between answer and ground truth
  - Precision / Recall   : Token-level precision and recall
  - MRR                  : Mean Reciprocal Rank of expected cases in citations
  - nDCG                 : Normalised Discounted Cumulative Gain of citations
  - Faithfulness (token) : Fraction of answer sentences grounded in context (heuristic)
  - Hallucination Rate   : 1 - faithfulness
  - LLM-Judge Scores     : Faithfulness, Answer Relevance, Citation Correctness 1–5
  - Latency              : End-to-end response time in milliseconds
  - Answerable Accuracy  : Fraction of answerable questions answered (not refused)
  - Unanswerable Acc     : Fraction of unanswerable questions correctly refused

Usage:
    python ai/evaluation/ragas_eval.py \\
        --questions ai/evaluation/eval_questions.json \\
        --output ai/evaluation/results.json \\
        --top-k 5 \\
        [--llm-judge] \\
        [--judge-model claude-haiku-4-5-20251001]
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

_INSUFFICIENT = "does not contain sufficient evidence"

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
    if not expected_cases:
        return 1.0
    for rank, citation in enumerate(citations, 1):
        name = getattr(citation, "case_name", "") or ""
        if any(exp.lower() in name.lower() or name.lower() in exp.lower()
               for exp in expected_cases):
            return 1.0 / rank
    return 0.0


def ndcg(citations: list[Any], expected_cases: list[str], k: int = 5) -> float:
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
# LLM-as-judge
# ---------------------------------------------------------------------------

_JUDGE_PROMPT = """You are an impartial legal RAG evaluator. Score the following on a scale of 1–5.

QUESTION: {question}

RETRIEVED CONTEXT:
{context}

ANSWER: {answer}

CITATIONS USED: {citations}

Score each dimension strictly 1–5 (integer only):
1. Faithfulness: Does every claim in the answer appear in the retrieved context? (5=fully grounded, 1=fabricated)
2. Answer Relevance: Does the answer address the question asked? (5=directly answers, 1=completely off-topic)
3. Citation Correctness: Are the inline [N] citations accurate? (5=all correct, 1=all wrong or missing)

Return ONLY a JSON object:
{{"faithfulness": <1-5>, "answer_relevance": <1-5>, "citation_correctness": <1-5>}}"""


async def llm_judge(
    question: str,
    answer: str,
    context_text: str,
    citations: list[Any],
    judge_model: str,
) -> dict[str, int]:
    """Score a single answer using an LLM judge. Returns dict with 1-5 scores."""
    import os
    citation_names = [getattr(c, "case_name", "") for c in citations]
    prompt = _JUDGE_PROMPT.format(
        question=question,
        context=context_text[:3000],
        answer=answer[:2000],
        citations=", ".join(citation_names) or "none",
    )
    try:
        # Resolve judge via config (honours LLM_PROVIDER / model override)
        from app.services.ai.llm_provider import generate_text
        from app.services.ai.json_parser import parse_llm_json
        from pydantic import BaseModel

        class _JudgeScores(BaseModel):
            faithfulness: int = 3
            answer_relevance: int = 3
            citation_correctness: int = 3

        raw = await generate_text(prompt)
        result = await parse_llm_json(raw, _JudgeScores)
        return {
            "judge_faithfulness": max(1, min(5, result.faithfulness)),
            "judge_answer_relevance": max(1, min(5, result.answer_relevance)),
            "judge_citation_correctness": max(1, min(5, result.citation_correctness)),
        }
    except Exception as exc:
        print(f"    [warn] LLM judge failed: {exc}")
        return {"judge_faithfulness": -1, "judge_answer_relevance": -1, "judge_citation_correctness": -1}


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

async def evaluate(
    questions_path: str,
    output_path: str,
    top_k: int = 5,
    use_llm_judge: bool = False,
    judge_model: str = "claude-haiku-4-5-20251001",
) -> None:
    from app.services.ai.rag_pipeline import RAGPipeline

    with open(questions_path, encoding="utf-8") as f:
        eval_set: list[dict] = json.load(f)

    pipeline = RAGPipeline()
    results = []

    mode = f"top_k={top_k}" + (" | LLM-judge" if use_llm_judge else "")
    print(f"\nChronoLegal RAG Evaluation — {len(eval_set)} questions | {mode}")
    print("=" * 70)

    answerable_correct = 0
    answerable_total = 0
    unanswerable_correct = 0
    unanswerable_total = 0

    for i, item in enumerate(eval_set, 1):
        question = item["question"]
        ground_truth = item.get("ground_truth", "")
        expected_cases = item.get("expected_cases", [])
        category = item.get("category", "unknown")
        is_answerable = item.get("answerable", True)

        start = time.perf_counter()
        result = await pipeline.run(query=question, top_k=top_k)
        latency_ms = int((time.perf_counter() - start) * 1000)

        answered = _INSUFFICIENT not in result.answer

        # Answerable / unanswerable accuracy tracking
        if is_answerable:
            answerable_total += 1
            if answered:
                answerable_correct += 1
        else:
            unanswerable_total += 1
            if not answered:
                unanswerable_correct += 1

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

        judge_scores: dict = {}
        if use_llm_judge:
            judge_scores = await llm_judge(
                question, result.answer, context_text, result.citations, judge_model
            )

        entry = {
            "question": question,
            "category": category,
            "answerable": is_answerable,
            "answer": result.answer[:500] + "..." if len(result.answer) > 500 else result.answer,
            "ground_truth": ground_truth,
            "expected_cases": expected_cases,
            "citations_returned": [getattr(c, "case_name", "") for c in result.citations],
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
                **judge_scores,
            },
        }
        results.append(entry)

        judge_str = ""
        if use_llm_judge and judge_scores.get("judge_faithfulness", -1) > 0:
            judge_str = (
                f" J-F={judge_scores['judge_faithfulness']}"
                f" J-R={judge_scores['judge_answer_relevance']}"
                f" J-C={judge_scores['judge_citation_correctness']}"
            )

        print(
            f"  [{i:2d}/{len(eval_set)}] [{category[:12]:12s}] "
            f"EM={em:.2f} F1={f1:.2f} MRR={rr:.2f} "
            f"Faith={faith:.2f} Halluc={halluc:.2f} {latency_ms}ms"
            + judge_str
        )

    # ------------------------------------------------------------------
    # Aggregate metrics
    # ------------------------------------------------------------------
    n = len(results)

    def avg(key: str) -> float:
        vals = [r["metrics"][key] for r in results if r["metrics"].get(key, -1) >= 0]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    # Per-category breakdown
    categories = sorted({r["category"] for r in results})
    by_category: dict[str, dict] = {}
    for cat in categories:
        cat_results = [r for r in results if r["category"] == cat]
        by_category[cat] = {
            "count": len(cat_results),
            "avg_f1": round(sum(r["metrics"]["f1"] for r in cat_results) / len(cat_results), 4),
            "avg_mrr": round(sum(r["metrics"]["mrr"] for r in cat_results) / len(cat_results), 4),
        }

    aggregate: dict[str, Any] = {
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
        "answerable_accuracy": round(answerable_correct / answerable_total * 100, 1) if answerable_total else 0.0,
        "unanswerable_accuracy": round(unanswerable_correct / unanswerable_total * 100, 1) if unanswerable_total else 0.0,
    }
    if use_llm_judge:
        aggregate["judge_faithfulness_avg"] = avg("judge_faithfulness")
        aggregate["judge_answer_relevance_avg"] = avg("judge_answer_relevance")
        aggregate["judge_citation_correctness_avg"] = avg("judge_citation_correctness")

    summary = {
        "evaluation_config": {
            "total_questions": n,
            "top_k": top_k,
            "llm_judge": use_llm_judge,
            "judge_model": judge_model if use_llm_judge else None,
        },
        "aggregate_metrics": aggregate,
        "by_category": by_category,
        "results": results,
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    m = summary["aggregate_metrics"]
    print(f"\n{'=' * 70}")
    print(f"  Exact Match           : {m['exact_match']:.4f}")
    print(f"  Precision             : {m['precision']:.4f}")
    print(f"  Recall                : {m['recall']:.4f}")
    print(f"  F1 Score              : {m['f1']:.4f}")
    print(f"  MRR                   : {m['mrr']:.4f}")
    print(f"  nDCG@{top_k}               : {m['ndcg']:.4f}")
    print(f"  Faithfulness (token)  : {m['faithfulness']:.4f}")
    print(f"  Hallucination Rate    : {m['hallucination_rate']:.4f}")
    print(f"  Avg Latency           : {m['avg_latency_ms']:.0f}ms")
    print(f"  Sufficient Ctx        : {m['sufficient_context_pct']:.1f}%")
    print(f"  Answerable Accuracy   : {m['answerable_accuracy']:.1f}%")
    print(f"  Unanswerable Accuracy : {m['unanswerable_accuracy']:.1f}%")
    if use_llm_judge:
        print(f"  Judge Faithfulness    : {m.get('judge_faithfulness_avg', 0):.2f}/5")
        print(f"  Judge Relevance       : {m.get('judge_answer_relevance_avg', 0):.2f}/5")
        print(f"  Judge Citations       : {m.get('judge_citation_correctness_avg', 0):.2f}/5")
    print(f"\n  Category breakdown:")
    for cat, stats in by_category.items():
        print(f"    {cat:<20} n={stats['count']} F1={stats['avg_f1']:.3f} MRR={stats['avg_mrr']:.3f}")
    print(f"\n  Results saved → {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate ChronoLegal RAG pipeline")
    parser.add_argument("--questions", default="ai/evaluation/eval_questions.json")
    parser.add_argument("--output", default="ai/evaluation/results.json")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--llm-judge", action="store_true",
                        help="Enable LLM-as-judge scoring (faithfulness/relevance/citations 1–5)")
    parser.add_argument("--judge-model", default="claude-haiku-4-5-20251001",
                        help="Model to use for LLM judging (any configured provider)")
    args = parser.parse_args()
    asyncio.run(evaluate(
        args.questions,
        args.output,
        args.top_k,
        use_llm_judge=args.llm_judge,
        judge_model=args.judge_model,
    ))
