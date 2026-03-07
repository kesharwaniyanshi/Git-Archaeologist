"""
Candidate Retrieval - Select relevant commits based on user query.
Uses hybrid approach: keyword matching + semantic similarity (when available).
"""

import re
from typing import Optional
from datetime import datetime, timedelta


def retrieve_candidates_keyword(query: str, commits_index: list[dict], top_k: int = 50) -> list[dict]:
    """
    Fast keyword-based candidate retrieval.
    
    Scores commits based on:
    - Keyword matches in commit message
    - File path matches (e.g., "auth" matches "src/auth.py")
    - Recency (newer commits score slightly higher)
    
    Args:
        query: User's question (e.g., "Why was auth changed?")
        commits_index: List of lightweight commit metadata
        top_k: Number of candidates to return
    
    Returns:
        Top-k commits sorted by relevance score
    """
    # Extract keywords from query
    keywords = _extract_keywords(query)
    
    scored_commits = []
    
    for commit in commits_index:
        score = 0.0
        
        # Score: keyword matches in message
        message_lower = commit["message"].lower()
        for keyword in keywords:
            if keyword in message_lower:
                score += 10.0  # High weight for message matches
        
        # Score: keyword matches in file paths
        for file_info in commit["files_touched"]:
            filename_lower = file_info["filename"].lower()
            for keyword in keywords:
                if keyword in filename_lower:
                    score += 5.0  # Medium weight for path matches
        
        # Score: Recency bonus (commits from last 6 months get boost)
        commit_date = datetime.fromisoformat(commit["date"])
        days_ago = (datetime.now(commit_date.tzinfo) - commit_date).days
        if days_ago < 180:  # 6 months
            score += 2.0 - (days_ago / 180.0)  # Up to +2 for very recent
        
        # Score: Change size (larger changes often more important)
        if commit["total_changes"] > 100:
            score += 1.0
        
        scored_commits.append({
            "commit": commit,
            "score": score,
        })
    
    # Sort by score descending
    scored_commits.sort(key=lambda x: x["score"], reverse=True)
    
    # Return top-k candidates
    return [item["commit"] for item in scored_commits[:top_k]]


def _extract_keywords(query: str) -> list[str]:
    """
    Extract meaningful keywords from user query.
    
    Removes stop words and extracts technical terms.
    
    Args:
        query: User's natural language question
    
    Returns:
        List of keywords
    """
    # Convert to lowercase
    query_lower = query.lower()
    
    # Remove stop words
    stop_words = {
        "what", "why", "how", "when", "where", "who", "which", "is", "are", "was", "were",
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
        "from", "by", "about", "into", "through", "during", "before", "after", "above",
        "below", "between", "under", "again", "further", "then", "once", "here", "there",
        "all", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor",
        "not", "only", "own", "same", "so", "than", "too", "very", "can", "will", "just",
        "should", "now", "did", "does", "changed", "added", "fixed", "removed", "updated"
    }
    
    # Tokenize and filter
    words = re.findall(r'\b[a-z_]+\b', query_lower)
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    return keywords


def filter_by_date_range(commits: list[dict], start_date: Optional[str] = None, 
                         end_date: Optional[str] = None) -> list[dict]:
    """
    Filter commits by date range.
    
    Args:
        commits: List of commit metadata
        start_date: ISO format date string (e.g., "2025-01-01")
        end_date: ISO format date string
    
    Returns:
        Filtered list of commits
    """
    filtered = []
    
    for commit in commits:
        commit_date = datetime.fromisoformat(commit["date"])
        
        if start_date:
            start = datetime.fromisoformat(start_date)
            if commit_date < start:
                continue
        
        if end_date:
            end = datetime.fromisoformat(end_date)
            if commit_date > end:
                continue
        
        filtered.append(commit)
    
    return filtered


def filter_by_file_pattern(commits: list[dict], file_pattern: str) -> list[dict]:
    """
    Filter commits that touched files matching a pattern.
    
    Args:
        commits: List of commit metadata
        file_pattern: Regex pattern or substring (e.g., "auth" or "src/.*\.py")
    
    Returns:
        Commits that touched matching files
    """
    filtered = []
    pattern = re.compile(file_pattern, re.IGNORECASE)
    
    for commit in commits:
        for file_info in commit["files_touched"]:
            if pattern.search(file_info["filename"]):
                filtered.append(commit)
                break  # Only add once per commit
    
    return filtered
