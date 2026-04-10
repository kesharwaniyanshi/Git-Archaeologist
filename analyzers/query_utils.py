"""Utility functions for lightweight commit indexing and candidate selection."""

from __future__ import annotations

from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List
import json
import re

from dotenv import load_dotenv
from pydriller import Repository

from core.github_fetcher import (
    get_commit_detail,
    is_github_repo_url,
    list_repo_commits,
    parse_github_repo_url,
    transform_github_commit_detail,
)

# Ensure GROQ_API_KEY and other env vars are available for analyzer initialization.
load_dotenv()


# In-memory cache for GitHub commit details keyed by "owner/repo" -> sha -> payload.
_GITHUB_COMMIT_CACHE: Dict[str, Dict[str, Dict]] = {}


def _github_cache_key(repo_url: str) -> str:
    owner, repo = parse_github_repo_url(repo_url)
    return f"{owner}/{repo}"


def _parse_commit_datetime(value: str) -> datetime:
    """Parse commit datetime values from both PyDriller and GitHub API payloads."""
    raw = (value or "").strip()
    if not raw:
        return datetime.fromtimestamp(0)

    # GitHub API timestamps are usually RFC3339 with a trailing Z.
    # Python 3.9 datetime.fromisoformat does not accept plain Z suffix.
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        # Keep retrieval robust even if a timestamp is malformed.
        return datetime.fromtimestamp(0)


def ingest_light(repo_path: str, max_commits: int = 1000) -> List[Dict]:
    """Extract commit metadata without loading full diffs."""
    if is_github_repo_url(repo_path):
        owner, repo = parse_github_repo_url(repo_path)
        commits = list_repo_commits(owner, repo, per_page=max_commits)

        # Keep indexing lightweight: defer expensive per-commit diff fetches
        # to fetch_diffs_for_commits() for only top-ranked candidates.
        parsed: List[Dict] = []
        for item in commits[:max_commits]:
            commit_block = item.get("commit") or {}
            author_block = commit_block.get("author") or {}
            sha = item.get("sha") or ""
            if not sha:
                continue

            parsed.append(
                {
                    "hash": sha,
                    "short_hash": sha[:8],
                    "message": commit_block.get("message", ""),
                    "author": author_block.get("name") or "Unknown",
                    "date": author_block.get("date") or "",
                    "files": [],
                }
            )

        return parsed

    commits: List[Dict] = []
    repo = Repository(repo_path)

    for idx, commit in enumerate(repo.traverse_commits()):
        if idx >= max_commits:
            break

        file_list = [mf.filename for mf in commit.modified_files]
        commits.append(
            {
                "hash": commit.hash,
                "short_hash": commit.hash[:8],
                "message": commit.msg,
                "author": commit.author.name,
                "date": commit.author_date.isoformat(),
                "files": file_list,
            }
        )

    return commits


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", (text or "").lower())


def message_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a or "", b or "").ratio()


def candidate_commit_scores(query: str, commits: List[Dict]) -> Dict[str, float]:
    """Return retrieval scores keyed by commit hash."""
    if not commits:
        return {}

    dates = [_parse_commit_datetime(c.get("date", "")) for c in commits]
    max_ts = max(dates).timestamp()
    min_ts = min(dates).timestamp()
    ts_range = max_ts - min_ts if max_ts != min_ts else 1.0

    q_tokens = set(tokenize(query))
    scores: Dict[str, float] = {}

    for commit in commits:
        msg_score = message_similarity(query, commit.get("message", ""))

        filename_score = 0.0
        for file_obj in commit.get("files", []):
            filename = file_obj.get("filename", "") if isinstance(file_obj, dict) else str(file_obj)
            if q_tokens & set(tokenize(filename)):
                filename_score = 1.0
                break

        commit_ts = _parse_commit_datetime(commit.get("date", "")).timestamp()
        recency = (commit_ts - min_ts) / ts_range
        scores[commit["hash"]] = 0.35 * msg_score + 0.40 * filename_score + 0.25 * recency

    return scores


def candidate_commits(query: str, commits: List[Dict], top_n: int = 20) -> List[Dict]:
    """Return top commits ranked by candidate_commit_scores."""
    scores = candidate_commit_scores(query, commits)
    if not scores:
        return []

    by_hash = {commit["hash"]: commit for commit in commits}
    ranked_hashes = sorted(scores.keys(), key=lambda h: scores[h], reverse=True)
    return [by_hash[h] for h in ranked_hashes[:top_n] if h in by_hash]


def fetch_diffs_for_commits(repo_path: str, commit_hashes: List[str]) -> List[Dict]:
    """Fetch full diff payloads for selected commits only."""
    if is_github_repo_url(repo_path):
        owner, repo = parse_github_repo_url(repo_path)
        cache_key = _github_cache_key(repo_path)
        _GITHUB_COMMIT_CACHE.setdefault(cache_key, {})

        found: List[Dict] = []
        for sha in commit_hashes:
            cached = _GITHUB_COMMIT_CACHE[cache_key].get(sha)
            if cached:
                found.append(cached)
                continue

            detail = get_commit_detail(owner, repo, sha)
            transformed = transform_github_commit_detail(detail)
            _GITHUB_COMMIT_CACHE[cache_key][sha] = transformed
            found.append(transformed)

        by_hash = {item["hash"]: item for item in found}
        return [by_hash[h] for h in commit_hashes if h in by_hash]

    repo = Repository(repo_path)
    found: List[Dict] = []
    remaining = set(commit_hashes)

    for commit in repo.traverse_commits():
        if commit.hash not in remaining:
            continue

        files_changed = []
        for mf in commit.modified_files:
            files_changed.append(
                {
                    "filename": mf.filename,
                    "change_type": mf.change_type.name,
                    "additions": mf.added_lines,
                    "deletions": mf.deleted_lines,
                    "diff": mf.diff or "",
                }
            )

        found.append(
            {
                "hash": commit.hash,
                "message": commit.msg,
                "author": commit.author.name,
                "date": commit.author_date.isoformat(),
                "files_changed": files_changed,
            }
        )

        remaining.remove(commit.hash)
        if not remaining:
            break

    by_hash = {item["hash"]: item for item in found}
    return [by_hash[h] for h in commit_hashes if h in by_hash]


def save_commits_metadata(commits: List[Dict], out_path: str) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as handle:
        json.dump(commits, handle, indent=2)


def load_commits_metadata(path: str) -> List[Dict]:
    with open(path, "r") as handle:
        return json.load(handle)
