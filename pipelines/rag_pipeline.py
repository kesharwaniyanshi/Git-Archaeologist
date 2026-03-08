"""RAG retrieval pipeline orchestration and answer synthesis."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import time

from analyzers.query_analyzer import QueryDrivenAnalyzer
from analyzers.query_utils import candidate_commit_scores
from .rag_models import RetrievalResult
from .rag_processing import QueryFilter, ResultRanker


class RAGPipeline:
    """High-level retrieval and synthesis pipeline."""

    def __init__(self, analyzer: QueryDrivenAnalyzer, verbose: bool = True):
        self.analyzer = analyzer
        self.verbose = verbose
        self.query_filter = QueryFilter()
        self.result_ranker = ResultRanker()
        self.query_history: List[Tuple[str, List[RetrievalResult]]] = []

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        analyze_candidates: int = 20,
        deduplicate: bool = True,
        boost_freshness: bool = False,
        filter_authors: Optional[List[str]] = None,
        exclude_authors: Optional[List[str]] = None,
    ) -> List[RetrievalResult]:
        start_time = time.time()

        if self.verbose:
            print(f"\nRAG Retrieval: {query}")

        normalized_query = self.query_filter.normalize(query)
        summaries = self.analyzer.answer_question(
            query,
            top_k=analyze_candidates,
            analyze_candidates=analyze_candidates,
        )

        scores = candidate_commit_scores(query, self.analyzer.commits_index)
        results: List[RetrievalResult] = []
        cache_hits = 0

        for summary in summaries:
            commit_hash = summary.get("hash")
            commit_meta = next(
                (commit for commit in self.analyzer.commits_index if commit["hash"] == commit_hash),
                None,
            )
            if not commit_meta:
                continue

            result = RetrievalResult(
                commit_hash=commit_hash,
                short_hash=commit_meta.get("short_hash", commit_hash[:8]),
                message=commit_meta.get("message", ""),
                summary=summary.get("summary", ""),
                author=commit_meta.get("author", "Unknown"),
                date=commit_meta.get("date", ""),
                relevance_score=scores.get(commit_hash, 0.0),
                status=summary.get("status", "unknown"),
                error=summary.get("error"),
            )
            results.append(result)

            if summary.get("status") == "cached":
                cache_hits += 1

        if deduplicate:
            results = self.result_ranker.deduplicate_results(results)

        if boost_freshness:
            results = self.result_ranker.rank_by_freshness(results)

        if filter_authors:
            results = self.result_ranker.filter_by_authors(results, allowed_authors=filter_authors)

        if exclude_authors:
            results = self.result_ranker.filter_by_authors(results, excluded_authors=exclude_authors)

        results.sort(key=lambda item: item.relevance_score, reverse=True)
        results = results[:top_k]

        if self.verbose:
            elapsed = time.time() - start_time
            print(f"Retrieved {len(results)} results in {elapsed:.2f}s")
            print(f"Cache hits: {cache_hits}/{len(summaries)}")

        self.query_history.append((normalized_query, results))
        return results

    def batch_retrieve(self, queries: List[str], **retrieve_kwargs) -> Dict[str, List[RetrievalResult]]:
        return {query: self.retrieve(query, **retrieve_kwargs) for query in queries}

    def _deterministic_confidence(self, results: List[RetrievalResult]) -> Tuple[str, str, float]:
        if not results:
            return "Low", "No supporting commits were retrieved.", 0.0

        top = results[:5]
        avg_relevance = sum(max(0.0, min(1.0, item.relevance_score)) for item in top) / len(top)
        evidence_breadth = min(len(top), 5) / 5.0
        success_ratio = sum(1 for item in top if item.status != "error") / len(top)

        score = 0.5 * avg_relevance + 0.3 * evidence_breadth + 0.2 * success_ratio

        if score >= 0.75:
            return (
                "High",
                "Strong relevance across multiple supporting commits with mostly successful evidence.",
                score,
            )
        if score >= 0.45:
            return "Medium", "Useful evidence exists, but support depth or relevance is moderate.", score
        return "Low", "Limited or weakly relevant evidence supports this conclusion.", score

    def synthesize_answer(self, query: str, results: List[RetrievalResult]) -> str:
        if not results:
            return "No relevant commits were found for this question."

        evidence_lines = [
            f"- {item.short_hash} | {item.date} | {item.message}\n  Summary: {item.summary}"
            for item in results[:5]
        ]

        prompt = (
            "You are a software engineering assistant answering questions about Git history. "
            "Use only the evidence provided below. Do not invent facts. "
            "Answer the user's question directly and clearly, and keep the response focused on the question intent.\n\n"
            "Structure your response as:\n"
            "1) Direct answer to the question\n"
            "2) Key supporting evidence from the commits\n"
            "3) Why this change likely happened\n"
            "Do not include a confidence label in your response; confidence is added separately by the system.\n\n"
            "If evidence is partial or ambiguous, state that explicitly and explain what is missing.\n\n"
            f"Question: {query}\n\n"
            "Evidence:\n"
            + "\n".join(evidence_lines)
        )

        confidence_level, confidence_reason, confidence_score = self._deterministic_confidence(results)
        confidence_footer = (
            f"\n\nConfidence (deterministic): {confidence_level} "
            f"(score={confidence_score:.2f}) - {confidence_reason}"
        )

        try:
            answer = self.analyzer.summarizer._call_groq(prompt)
            return answer + confidence_footer
        except Exception:
            top = results[0]
            pieces = [
                f"Most relevant change: {top.message} ({top.short_hash}).",
                f"Likely reason: {top.summary}",
            ]
            if len(results) > 1:
                pieces.append(f"Related supporting commits: {', '.join(r.short_hash for r in results[1:4])}.")
            pieces.append(
                f"Confidence (deterministic): {confidence_level} "
                f"(score={confidence_score:.2f}) - {confidence_reason}"
            )
            return "\n".join(pieces)

    def export_results(self, results: List[RetrievalResult], output_file: str, include_history: bool = False) -> None:
        payload: Dict[str, object] = {"results": [item.to_dict() for item in results]}

        if include_history:
            payload["history"] = [
                {
                    "query": query,
                    "result_count": len(query_results),
                    "results": [item.to_dict() for item in query_results],
                }
                for query, query_results in self.query_history
            ]

        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as handle:
            json.dump(payload, handle, indent=2)

        if self.verbose:
            print(f"Exported results to {output_file}")

    def explain_result(self, result: RetrievalResult, detailed: bool = False) -> str:
        if not detailed:
            status_part = f" [{result.status}]" if result.status else ""
            return (
                f"{result.short_hash} - {result.message}\n"
                f"Score: {result.relevance_score:.3f}{status_part}\n"
                f"Summary: {result.summary}"
            )

        lines = [
            f"Commit: {result.short_hash}",
            f"Message: {result.message}",
            f"Author: {result.author}",
            f"Date: {result.date}",
            "",
            f"Summary: {result.summary}",
            "",
            f"Relevance Score: {result.relevance_score:.3f}",
            f"Status: {result.status}",
        ]

        if result.error:
            lines.append(f"Error: {result.error}")

        return "\n".join(lines)
