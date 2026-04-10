"""RAG retrieval pipeline orchestration and answer synthesis."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
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
        top_k: int = 20,
        analyze_candidates: int = 20,
        deduplicate: bool = True,
        boost_freshness: bool = False,
        filter_authors: Optional[List[str]] = None,
        exclude_authors: Optional[List[str]] = None,
        commit_filter: Optional[Callable[[Dict], bool]] = None,
    ) -> List[RetrievalResult]:
        start_time = time.time()

        if self.verbose:
            print(f"\nRAG Retrieval: {query}")

        normalized_query = self.query_filter.normalize(query)
        summaries = self.analyzer.answer_question(
            query,
            top_k=top_k,
            analyze_candidates=analyze_candidates,
            commit_filter=commit_filter,
        )

        scores = candidate_commit_scores(query, self.analyzer.commits_index)
        results: List[RetrievalResult] = []

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
                diff_snippets=summary.get("diff_snippet", ""),
                files_changed=summary.get("files_changed", []),
            )
            results.append(result)

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

        self.query_history.append((normalized_query, results))
        return results

    def batch_retrieve(self, queries: List[str], **retrieve_kwargs) -> Dict[str, List[RetrievalResult]]:
        return {query: self.retrieve(query, **retrieve_kwargs) for query in queries}

    def _deterministic_confidence(self, results: List[RetrievalResult]) -> Tuple[str, str, float]:
        if not results:
            return "Low", "No supporting commits were retrieved.", 0.0

        top = results[:10]
        avg_relevance = sum(max(0.0, min(1.0, item.relevance_score)) for item in top) / len(top)
        evidence_breadth = min(len(top), 10) / 10.0
        success_ratio = sum(1 for item in top if item.status != "error") / len(top)
        has_diffs = sum(1 for item in top if item.diff_snippets) / len(top)

        score = 0.35 * avg_relevance + 0.25 * evidence_breadth + 0.15 * success_ratio + 0.25 * has_diffs

        if score >= 0.70:
            return "High", "Strong code-level evidence across multiple commits.", score
        if score >= 0.40:
            return "Medium", "Useful evidence exists, but some commits lack detailed diffs.", score
        return "Low", "Limited or weakly relevant evidence supports this conclusion.", score

    def synthesize_answer(
        self,
        query: str,
        results: List[RetrievalResult],
        conversation_history: Optional[List[Dict]] = None,
        contributor_mode: bool = False,
        contributor_label: str = "",
    ) -> str:
        """Synthesize a natural answer using raw diff evidence and optional conversation history."""
        if not results:
            return "No relevant commits were found for this question."

        # Build rich evidence blocks with actual code diffs
        evidence_blocks = []
        for item in results[:10]:
            block = f"### Commit {item.short_hash} by {item.author} ({item.date})\n"
            block += f"Message: {item.message}\n"
            if item.files_changed:
                block += f"Files: {', '.join(item.files_changed[:8])}\n"
            if item.diff_snippets:
                block += f"\nCode changes:\n```\n{item.diff_snippets[:3000]}\n```\n"
            evidence_blocks.append(block)

        evidence_text = "\n".join(evidence_blocks)

        module_hint = ""
        if contributor_mode:
            from analyzers.contributor_intent import module_touch_summary

            summary = module_touch_summary(results)
            if summary:
                module_hint = summary + "\n\n"

        # Build conversation context for multi-turn
        history_text = ""
        if conversation_history:
            history_lines = []
            for turn in conversation_history[-6:]:  # Last 6 turns max
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if content:
                    history_lines.append(f"{role.upper()}: {content[:500]}")
            if history_lines:
                history_text = "Previous conversation:\n" + "\n".join(history_lines) + "\n\n"

        if contributor_mode:
            who = contributor_label or "the contributor"
            system_prompt = (
                "You are Git Archaeologist. The user asked about a specific contributor's work. "
                f"Summarize {who}'s impact using ONLY the commits and file paths in the evidence.\n\n"
                "Rules:\n"
                "- Organize the answer by themes and by top-level directory / module where helpful.\n"
                "- Mention roughly how activity is spread across areas (use the module summary when provided).\n"
                "- Cite short commit hashes inline. Note if the sample may not include every commit.\n"
                "- Write in natural language; avoid empty praise. Do NOT invent commits or files.\n"
                "- If this is a follow-up, use the conversation history.\n"
            )
        else:
            system_prompt = (
                "You are Git Archaeologist, an expert software forensics assistant. "
                "You analyze Git repository history to answer questions about why and how code evolved.\n\n"
                "Rules:\n"
                "- Ground every claim in the commit evidence provided. Cite commit hashes inline (e.g., 'in abc12345').\n"
                "- When code diffs are available, reference specific lines, functions, or patterns you can see in them.\n"
                "- Write naturally and conversationally. Avoid rigid numbered lists unless truly helpful.\n"
                "- If the evidence is partial or ambiguous, say so explicitly.\n"
                "- If this is a follow-up question, use the conversation history for context.\n"
                "- Do NOT invent information. Do NOT include a confidence label.\n"
            )

        user_prompt = (
            f"{history_text}"
            f"Question: {query}\n\n"
            f"{module_hint}"
            f"Repository evidence:\n{evidence_text}"
        )

        confidence_level, confidence_reason, confidence_score = self._deterministic_confidence(results)

        try:
            answer = self.analyzer.summarizer._call_groq_synthesis(system_prompt, user_prompt)
            return answer
        except Exception:
            # Fallback: build a basic answer without LLM
            top = results[0]
            pieces = [
                f"Based on the repository history, the most relevant change is {top.short_hash}: \"{top.message}\".",
            ]
            if top.diff_snippets:
                pieces.append(f"\nKey code changes:\n```\n{top.diff_snippets[:1000]}\n```")
            if len(results) > 1:
                pieces.append(f"\nRelated commits: {', '.join(r.short_hash for r in results[1:4])}.")
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
