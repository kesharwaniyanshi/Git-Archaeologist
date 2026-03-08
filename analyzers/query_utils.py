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

# Ensure GROQ_API_KEY and other env vars are available for analyzer initialization.
load_dotenv()


def ingest_light(repo_path: str, max_commits: int = 1000) -> List[Dict]:
    """Extract commit metadata without loading full diffs."""
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

    dates = [datetime.fromisoformat(c["date"]) for c in commits]
    max_ts = max(dates).timestamp()
    min_ts = min(dates).timestamp()
    ts_range = max_ts - min_ts if max_ts != min_ts else 1.0

    q_tokens = set(tokenize(query))
    scores: Dict[str, float] = {}

    for commit in commits:
        msg_score = message_similarity(query, commit.get("message", ""))

        filename_score = 0.0
        for filename in commit.get("files", []):
            if q_tokens & set(tokenize(filename)):
                filename_score = 1.0
                break

        commit_ts = datetime.fromisoformat(commit["date"]).timestamp()
        recency = (commit_ts - min_ts) / ts_range
        scores[commit["hash"]] = 0.6 * msg_score + 0.3 * filename_score + 0.1 * recency

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
