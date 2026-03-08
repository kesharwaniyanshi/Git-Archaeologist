"""
RAG (Retrieval-Augmented Generation) Retrieval Pipeline.

Orchestrates full workflow:
1. Query → semantic + heuristic ranking
2. Retrieve candidate commits
3. Fetch diffs for candidates
4. Summarize with LLM
5. Rank and deduplicate results

Provides both single-query and batch-query interfaces.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from query_analyzer import QueryDrivenAnalyzer, fetch_diffs_for_commits


@dataclass
class RetrievalResult:
    """Single result from RAG retrieval pipeline."""
    
    commit_hash: str
    short_hash: str
    message: str
    summary: str
    author: str
    date: str
    relevance_score: float
    status: str
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dict for JSON serialization."""
        return {
            "commit_hash": self.commit_hash,
            "short_hash": self.short_hash,
            "message": self.message,
            "summary": self.summary,
            "author": self.author,
            "date": self.date,
            "relevance_score": self.relevance_score,
            "status": self.status,
            "error": self.error,
        }


@dataclass
class QueryMetadata:
    """Track per-query metadata for debugging and optimization."""
    
    query: str
    timestamp: str
    candidates_evaluated: int
    summaries_generated: int
    cache_hits: int
    elapsed_seconds: float
    
    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "timestamp": self.timestamp,
            "candidates_evaluated": self.candidates_evaluated,
            "summaries_generated": self.summaries_generated,
            "cache_hits": self.cache_hits,
            "elapsed_seconds": self.elapsed_seconds,
        }


class QueryFilter:
    """Pre-processing for user queries."""
    
    @staticmethod
    def normalize(query: str) -> str:
        """Normalize query: lowercase, strip whitespace."""
        return query.strip().lower()
    
    @staticmethod
    def extract_date_range(query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract date range hints from query.
        
        Examples:
          "changes in last 3 months" → recent~90d
          "changes before 2026-01" → before~2026-01-01
          "changes in 2025" → 2025-01-01 to 2025-12-31
        
        Returns: (start_iso, end_iso) or (None, None) if not found
        """
        # Simplified heuristic (can be enhanced with regex/NLP)
        query_lower = query.lower()
        
        if "last" in query_lower and "month" in query_lower:
            # Rough estimate: assume last X months from today
            import datetime as dt
            today = dt.date.today()
            try:
                months = int(query.split()[-3])  # e.g., "last 3 months"
                days_back = months * 30
                start_date = (today - dt.timedelta(days=days_back)).isoformat()
                return start_date, None
            except (ValueError, IndexError):
                pass
        
        return None, None
    
    @staticmethod
    def extract_file_patterns(query: str) -> List[str]:
        """
        Extract filename/path patterns from query.
        
        Examples:
          "changes to auth.py" → ["auth.py"]
          "database changes" → ["database", "db"]
        
        Returns: list of patterns
        """
        patterns = []
        query_lower = query.lower()
        
        # Look for ".py", ".ts", etc.
        import re
        file_patterns = re.findall(r'\b\w+\.\w+\b', query_lower)
        patterns.extend(file_patterns)
        
        # Look for common module names
        keywords = {
            "auth": ["auth", "login", "password"],
            "database": ["database", "db", "sql"],
            "api": ["api", "endpoint", "rest"],
            "ui": ["ui", "frontend", "component"],
        }
        
        for key, terms in keywords.items():
            if any(term in query_lower for term in terms):
                patterns.append(key)
        
        return patterns


class ResultRanker:
    """Post-processing and ranking of RAG results."""
    
    @staticmethod
    def deduplicate_results(
        results: List[RetrievalResult],
        by_summary: bool = False,
    ) -> List[RetrievalResult]:
        """
        Remove duplicate results.
        
        Args:
            results: List of RetrievalResult objects
            by_summary: If True, also deduplicate by summary (fuzzy match)
        
        Returns:
            Deduplicated results
        """
        seen_hashes = set()
        deduplicated = []
        
        for result in results:
            if result.commit_hash not in seen_hashes:
                deduplicated.append(result)
                seen_hashes.add(result.commit_hash)
        
        return deduplicated
    
    @staticmethod
    def rank_by_freshness(
        results: List[RetrievalResult],
        weight: float = 0.1,
    ) -> List[RetrievalResult]:
        """
        Boost score of recent commits.
        
        Args:
            results: List of results
            weight: Freshness weight (0-1)
        
        Returns:
            Re-ranked results
        """
        if not results:
            return results
        
        # Parse dates
        dates = []
        for r in results:
            try:
                dt = datetime.fromisoformat(r.date)
                dates.append(dt)
            except ValueError:
                dates.append(None)
        
        # Find date range
        valid_dates = [d for d in dates if d is not None]
        if not valid_dates:
            return results
        
        max_date = max(valid_dates)
        min_date = min(valid_dates)
        if max_date == min_date:
            return results
        
        date_range = (max_date - min_date).total_seconds()
        
        # Update scores
        for i, result in enumerate(results):
            if dates[i] is not None:
                freshness = (dates[i] - min_date).total_seconds() / date_range
                result.relevance_score = (
                    (1 - weight) * result.relevance_score + weight * freshness
                )
        
        # Re-sort
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results
    
    @staticmethod
    def filter_by_authors(
        results: List[RetrievalResult],
        allowed_authors: Optional[List[str]] = None,
        excluded_authors: Optional[List[str]] = None,
    ) -> List[RetrievalResult]:
        """
        Filter results by author whitelist/blacklist.
        
        Args:
            results: List of results
            allowed_authors: Only include these authors
            excluded_authors: Exclude these authors
        
        Returns:
            Filtered results
        """
        filtered = []
        
        for result in results:
            if allowed_authors and result.author not in allowed_authors:
                continue
            if excluded_authors and result.author in excluded_authors:
                continue
            filtered.append(result)
        
        return filtered


class RAGPipeline:
    """
    High-level RAG orchestrator combining:
    - Query preprocessing
    - Semantic/heuristic retrieval
    - Summarization
    - Result ranking
    """
    
    def __init__(
        self,
        analyzer: QueryDrivenAnalyzer,
        verbose: bool = True,
    ):
        """
        Initialize RAG pipeline with an analyzer instance.
        
        Args:
            analyzer: QueryDrivenAnalyzer with indexed repository
            verbose: Print progress messages
        """
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
        """
        Run full RAG retrieval pipeline on a query.
        
        Args:
            query: User's natural language question
            top_k: Max results to return
            analyze_candidates: Candidates to analyze before ranking
            deduplicate: Remove duplicate results
            boost_freshness: Weight recent commits higher
            filter_authors: Whitelist authors
            exclude_authors: Blacklist authors
        
        Returns:
            Top-k RetrievalResult objects
        """
        import time
        start_time = time.time()
        
        if self.verbose:
            print(f"\n🔍 RAG Retrieval: {query}")
        
        # Normalize query
        normalized_query = self.query_filter.normalize(query)
        
        # Retrieve summaries (this calls analyzer.answer_question)
        summaries = self.analyzer.answer_question(
            query,
            top_k=analyze_candidates,
            analyze_candidates=analyze_candidates,
        )
        
        # Convert summaries to RetrievalResult objects
        results = []
        cache_hits = 0
        
        for summary in summaries:
            # Find commit metadata
            commit_hash = summary.get("hash")
            commit_meta = next(
                (c for c in self.analyzer.commits_index if c["hash"] == commit_hash),
                None,
            )
            
            if not commit_meta:
                continue
            
            # Calculate relevance from analyzer cache
            from query_analyzer import _candidate_commit_scores
            scores = _candidate_commit_scores(query, self.analyzer.commits_index)
            score = scores.get(commit_hash, 0.0)
            
            result = RetrievalResult(
                commit_hash=commit_hash,
                short_hash=commit_meta.get("short_hash", commit_hash[:8]),
                message=commit_meta.get("message", ""),
                summary=summary.get("summary", ""),
                author=commit_meta.get("author", "Unknown"),
                date=commit_meta.get("date", ""),
                relevance_score=score,
                status=summary.get("status", "unknown"),
                error=summary.get("error"),
            )
            results.append(result)
            
            if summary.get("status") == "cached":
                cache_hits += 1
        
        # Post-processing
        if deduplicate:
            results = self.result_ranker.deduplicate_results(results)
        
        if boost_freshness:
            results = self.result_ranker.rank_by_freshness(results)
        
        if filter_authors:
            results = self.result_ranker.filter_by_authors(
                results,
                allowed_authors=filter_authors,
            )
        
        if exclude_authors:
            results = self.result_ranker.filter_by_authors(
                results,
                excluded_authors=exclude_authors,
            )
        
        # Sort by relevance and trim
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        results = results[:top_k]
        
        elapsed = time.time() - start_time
        
        if self.verbose:
            print(f"✅ Retrieved {len(results)} results in {elapsed:.2f}s")
            print(f"   Cache hits: {cache_hits}/{len(summaries)}")
        
        # Track in history
        self.query_history.append((normalized_query, results))
        
        return results
    
    def batch_retrieve(
        self,
        queries: List[str],
        **retrieve_kwargs,
    ) -> Dict[str, List[RetrievalResult]]:
        """
        Run multiple queries.
        
        Args:
            queries: List of questions
            **retrieve_kwargs: Passed to retrieve()
        
        Returns:
            Dict mapping query → results
        """
        results = {}
        for query in queries:
            results[query] = self.retrieve(query, **retrieve_kwargs)
        return results

    def _deterministic_confidence(self, results: List[RetrievalResult]) -> Tuple[str, str, float]:
        """
        Compute deterministic confidence from evidence quality.

        Combines:
        - average relevance score (top results)
        - evidence breadth (number of supporting commits)
        - success ratio (non-error retrievals)
        """
        if not results:
            return "Low", "No supporting commits were retrieved.", 0.0

        top = results[:5]
        avg_relevance = sum(max(0.0, min(1.0, r.relevance_score)) for r in top) / len(top)
        evidence_breadth = min(len(top), 5) / 5.0
        success_ratio = sum(1 for r in top if r.status != "error") / len(top)

        score = 0.5 * avg_relevance + 0.3 * evidence_breadth + 0.2 * success_ratio

        if score >= 0.75:
            level = "High"
            reason = "Strong relevance across multiple supporting commits with mostly successful evidence."
        elif score >= 0.45:
            level = "Medium"
            reason = "Useful evidence exists, but support depth or relevance is moderate."
        else:
            level = "Low"
            reason = "Limited or weakly relevant evidence supports this conclusion."

        return level, reason, score

    def synthesize_answer(
        self,
        query: str,
        results: List[RetrievalResult],
    ) -> str:
        """
        Synthesize one user-facing answer from retrieved commit evidence.

        Falls back to a deterministic summary if LLM synthesis fails.
        """
        if not results:
            return "No relevant commits were found for this question."

        evidence_lines = []
        for r in results[:5]:
            evidence_lines.append(
                f"- {r.short_hash} | {r.date} | {r.message}\n  Summary: {r.summary}"
            )

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
            # Reuse existing summarizer client to avoid duplicate LLM setup.
            answer = self.analyzer.summarizer._call_groq(prompt)
            return answer + confidence_footer
        except Exception:
            # Deterministic fallback for reliability.
            top = results[0]
            parts = [
                f"Most relevant change: {top.message} ({top.short_hash}).",
                f"Likely reason: {top.summary}",
            ]
            if len(results) > 1:
                related = ", ".join(r.short_hash for r in results[1:4])
                parts.append(f"Related supporting commits: {related}.")
            parts.append(
                f"Confidence (deterministic): {confidence_level} "
                f"(score={confidence_score:.2f}) - {confidence_reason}"
            )
            return "\n".join(parts)
    
    def export_results(
        self,
        results: List[RetrievalResult],
        output_file: str,
        include_history: bool = False,
    ) -> None:
        """
        Export results to JSON file.
        
        Args:
            results: List of RetrievalResult objects
            output_file: Output file path
            include_history: Also export query history
        """
        data = {
            "results": [r.to_dict() for r in results],
        }
        
        if include_history:
            data["history"] = [
                {
                    "query": q,
                    "result_count": len(r),
                    "results": [re.to_dict() for re in r],
                }
                for q, r in self.query_history
            ]
        
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
        
        if self.verbose:
            print(f"💾 Exported results to {output_file}")
    
    def explain_result(
        self,
        result: RetrievalResult,
        detailed: bool = False,
    ) -> str:
        """
        Generate human-readable explanation for a result.
        
        Args:
            result: RetrievalResult object
            detailed: Include extended metadata and status details
        
        Returns:
            Formatted explanation string
        """
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


if __name__ == "__main__":
    import argparse
    
    p = argparse.ArgumentParser(description="RAG Retrieval Pipeline")
    p.add_argument("repo", help="Path to repository")
    p.add_argument("--query", required=True, help="Question to search")
    p.add_argument("--queries-file", help="File with queries (one per line)")
    p.add_argument("--top-k", type=int, default=5, help="Top K results")
    p.add_argument("--session-dir", help="Session directory for persistence")
    p.add_argument("--export", help="Export results to JSON")
    p.add_argument("--no-freshness-boost", action="store_true")
    p.add_argument("--no-embeddings", action="store_true")
    p.add_argument("--detailed-output", action="store_true", help="Show detailed per-result output")
    p.add_argument("--show-evidence", action="store_true", help="Also print commit-level evidence")
    args = p.parse_args()
    
    # Initialize analyzer
    analyzer = QueryDrivenAnalyzer(
        args.repo,
        use_embeddings=not args.no_embeddings,
        session_dir=args.session_dir,
    )
    
    # Load or index
    if args.session_dir:
        if not analyzer.load_session():
            analyzer.index_repository()
    else:
        analyzer.index_repository()
    
    # Create RAG pipeline
    rag = RAGPipeline(analyzer, verbose=True)
    
    # Single query
    if args.query:
        results = rag.retrieve(
            args.query,
            top_k=args.top_k,
            boost_freshness=not args.no_freshness_boost,
        )

        final_answer = rag.synthesize_answer(args.query, results)

        print("\n" + "=" * 80)
        print("Final Answer")
        print("=" * 80)
        print(final_answer)
        
        if args.show_evidence:
            print("\n" + "=" * 80)
            print("Evidence Commits")
            print("=" * 80)
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {rag.explain_result(result, detailed=args.detailed_output)}")
            print("=" * 80)
        
        if args.export:
            rag.export_results(results, args.export)
    
    # Batch queries from file
    elif args.queries_file:
        with open(args.queries_file, "r") as f:
            queries = [line.strip() for line in f if line.strip()]
        
        batch_results = rag.batch_retrieve(queries, top_k=args.top_k)
        
        for query, results in batch_results.items():
            print(f"\nQuery: {query}")
            print(f"Results: {len(results)}")
            for r in results[:3]:
                print(f"  - {r.short_hash}: {r.message[:40]}")
        
        if args.export:
            rag.export_results(
                [r for results in batch_results.values() for r in results],
                args.export,
                include_history=True,
            )
