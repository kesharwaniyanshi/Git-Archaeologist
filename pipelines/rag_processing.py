"""Query preprocessing and post-retrieval ranking helpers."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple
import re

from .rag_models import RetrievalResult


class QueryFilter:
    @staticmethod
    def normalize(query: str) -> str:
        return query.strip().lower()

    @staticmethod
    def extract_date_range(query: str) -> Tuple[Optional[str], Optional[str]]:
        query_lower = query.lower()
        if "last" in query_lower and "month" in query_lower:
            import datetime as dt

            today = dt.date.today()
            match = re.search(r"last\s+(\d+)\s+months?", query_lower)
            if match:
                months = int(match.group(1))
                days_back = months * 30
                start_date = (today - dt.timedelta(days=days_back)).isoformat()
                return start_date, None

        return None, None

    @staticmethod
    def extract_file_patterns(query: str) -> List[str]:
        patterns: List[str] = []
        query_lower = query.lower()

        patterns.extend(re.findall(r"\b\w+\.\w+\b", query_lower))

        keyword_buckets = {
            "auth": ["auth", "login", "password"],
            "database": ["database", "db", "sql"],
            "api": ["api", "endpoint", "rest"],
            "ui": ["ui", "frontend", "component"],
        }

        for label, terms in keyword_buckets.items():
            if any(term in query_lower for term in terms):
                patterns.append(label)

        return patterns


class ResultRanker:
    @staticmethod
    def deduplicate_results(results: List[RetrievalResult]) -> List[RetrievalResult]:
        seen_hashes = set()
        deduped: List[RetrievalResult] = []

        for result in results:
            if result.commit_hash in seen_hashes:
                continue
            deduped.append(result)
            seen_hashes.add(result.commit_hash)

        return deduped

    @staticmethod
    def rank_by_freshness(results: List[RetrievalResult], weight: float = 0.1) -> List[RetrievalResult]:
        if not results:
            return results

        dates = []
        for result in results:
            try:
                dates.append(datetime.fromisoformat(result.date))
            except ValueError:
                dates.append(None)

        valid_dates = [date for date in dates if date is not None]
        if not valid_dates:
            return results

        min_date = min(valid_dates)
        max_date = max(valid_dates)
        if min_date == max_date:
            return results

        date_span = (max_date - min_date).total_seconds()

        for idx, result in enumerate(results):
            if dates[idx] is None:
                continue
            freshness = (dates[idx] - min_date).total_seconds() / date_span
            result.relevance_score = (1 - weight) * result.relevance_score + weight * freshness

        results.sort(key=lambda item: item.relevance_score, reverse=True)
        return results

    @staticmethod
    def filter_by_authors(
        results: List[RetrievalResult],
        allowed_authors: Optional[List[str]] = None,
        excluded_authors: Optional[List[str]] = None,
    ) -> List[RetrievalResult]:
        filtered: List[RetrievalResult] = []

        for result in results:
            if allowed_authors and result.author not in allowed_authors:
                continue
            if excluded_authors and result.author in excluded_authors:
                continue
            filtered.append(result)

        return filtered
