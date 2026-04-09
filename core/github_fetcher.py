"""Utilities for fetching repository data from the GitHub REST API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests


GITHUB_API_BASE = "https://api.github.com"


@dataclass
class GitHubFetcherError(Exception):
    """Structured error raised for GitHub URL/API failures."""

    message: str
    status_code: int = 500

    def __str__(self) -> str:
        return self.message


def is_github_repo_url(value: str) -> bool:
    """Return True when value looks like a GitHub repository URL."""
    if not value:
        return False
    try:
        parsed = urlparse(value.strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and (parsed.netloc or "").lower() == "github.com"


def parse_github_repo_url(repo_url: str) -> Tuple[str, str]:
    """Parse a GitHub repository URL and return (owner, repo).

    Accepted examples:
    - https://github.com/owner/repo
    - https://github.com/owner/repo/
    - https://github.com/owner/repo.git
    - https://github.com/owner/repo/file.git
    - https://github.com/owner/repo/tree/main

    Raises:
        ValueError: If URL format is invalid or unsupported.
    """
    if not repo_url or not repo_url.strip():
        raise GitHubFetcherError("Invalid or empty GitHub URL.", status_code=400)

    raw = repo_url.strip()
    parsed = urlparse(raw)

    if parsed.scheme not in {"http", "https"}:
        raise GitHubFetcherError("Invalid GitHub URL: only http/https URLs are supported.", status_code=400)

    host = (parsed.netloc or "").lower()
    if host != "github.com":
        raise GitHubFetcherError("Invalid GitHub URL: expected host github.com.", status_code=400)

    # Extract owner/repo from the first two path segments and ignore any extras.
    # This allows URLs like /owner/repo/file.git or /owner/repo/tree/main.
    path = (parsed.path or "").strip("/")
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        raise GitHubFetcherError(
            "Invalid GitHub URL: expected format https://github.com/<owner>/<repo>.",
            status_code=400,
        )

    owner = parts[0].strip()
    repo = parts[1].strip()

    if repo.endswith(".git"):
        repo = repo[:-4]

    if not owner or not repo:
        raise GitHubFetcherError("Invalid GitHub URL: owner and repo must both be non-empty.", status_code=400)

    # Keep validation permissive: GitHub can introduce naming variations.
    if " " in owner or " " in repo:
        raise GitHubFetcherError("Invalid GitHub URL: owner/repo cannot contain spaces.", status_code=400)

    return owner, repo


def _build_headers(token: Optional[str] = None) -> Dict[str, str]:
    auth_token = (token or os.getenv("GITHUB_TOKEN") or "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "git-archaeologist/1.0",
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    return headers


def _handle_response_error(response: requests.Response) -> None:
    if response.status_code < 400:
        return

    text = (response.text or "").lower()
    remaining = response.headers.get("X-RateLimit-Remaining", "")
    reset_epoch = response.headers.get("X-RateLimit-Reset", "")
    reset_hint = ""
    if reset_epoch.isdigit():
        reset_at = datetime.fromtimestamp(int(reset_epoch), tz=timezone.utc).isoformat()
        reset_hint = f" Rate limit resets at {reset_at}."

    if response.status_code == 404:
        raise GitHubFetcherError(
            "Repository not found (404). Verify the owner/repo URL and ensure the repository is public.",
            status_code=404,
        )
    if response.status_code in {401, 403}:
        if "rate limit" in text or remaining == "0":
            raise GitHubFetcherError(
                "GitHub API rate limit exceeded. Set GITHUB_TOKEN in env to increase limits."
                + reset_hint,
                status_code=429,
            )
        raise GitHubFetcherError(
            "Repository is private or inaccessible with the current credentials.",
            status_code=403,
        )
    if response.status_code == 429:
        raise GitHubFetcherError(
            "GitHub API rate limit exceeded. Set GITHUB_TOKEN in env to increase limits."
            + reset_hint,
            status_code=429,
        )
    if response.status_code == 422:
        raise GitHubFetcherError(
            "Invalid commit reference for this repository. Re-index the selected GitHub URL to refresh commit hashes.",
            status_code=422,
        )

    raise GitHubFetcherError(
        f"GitHub API request failed with status {response.status_code}.",
        status_code=502,
    )


def list_repo_commits(owner: str, repo: str, per_page: int = 50, token: Optional[str] = None) -> List[Dict]:
    """Fetch repository commits from GitHub API."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits"
    try:
        response = requests.get(
            url,
            headers=_build_headers(token),
            params={"per_page": max(1, min(100, per_page))},
            timeout=20,
        )
    except requests.Timeout as exc:
        raise GitHubFetcherError("GitHub API timeout while listing commits.", status_code=504) from exc
    except requests.RequestException as exc:
        raise GitHubFetcherError("Network error while fetching commits from GitHub API.", status_code=502) from exc

    _handle_response_error(response)
    data = response.json()
    if not isinstance(data, list):
        raise GitHubFetcherError("Unexpected GitHub API response when listing commits.", status_code=502)
    return data


def get_commit_detail(owner: str, repo: str, sha: str, token: Optional[str] = None) -> Dict:
    """Fetch full commit detail (including changed files and patch) for one SHA."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{sha}"
    try:
        response = requests.get(url, headers=_build_headers(token), timeout=20)
    except requests.Timeout as exc:
        raise GitHubFetcherError(f"GitHub API timeout while fetching commit {sha[:8]}.", status_code=504) from exc
    except requests.RequestException as exc:
        raise GitHubFetcherError(
            f"Network error while fetching commit {sha[:8]} from GitHub API.",
            status_code=502,
        ) from exc

    _handle_response_error(response)
    data = response.json()
    if not isinstance(data, dict):
        raise GitHubFetcherError("Unexpected GitHub API response for commit detail.", status_code=502)
    return data


def transform_github_commit_detail(detail: Dict) -> Dict:
    """Map a GitHub commit detail response into the app's existing commit structure."""
    sha = detail.get("sha") or ""
    commit_block = detail.get("commit") or {}
    author_block = commit_block.get("author") or {}
    files = detail.get("files") or []

    files_changed = []
    for file_item in files:
        files_changed.append(
            {
                "filename": file_item.get("filename", ""),
                "change_type": str(file_item.get("status", "UNKNOWN")).upper(),
                "additions": int(file_item.get("additions") or 0),
                "deletions": int(file_item.get("deletions") or 0),
                "diff": file_item.get("patch") or "",
            }
        )

    return {
        "hash": sha,
        "short_hash": sha[:8],
        "commit_hash": sha,
        "message": commit_block.get("message", ""),
        "author": author_block.get("name") or "Unknown",
        "author_email": author_block.get("email") or "",
        "date": author_block.get("date") or "",
        "files": [f.get("filename", "") for f in files if f.get("filename")],
        "files_changed": files_changed,
    }


def fetch_repo_commits_with_diffs(
    owner: str,
    repo: str,
    max_commits: int = 50,
    token: Optional[str] = None,
) -> List[Dict]:
    """Fetch commits and per-commit file diffs, transformed for downstream pipeline use."""
    commits = list_repo_commits(owner, repo, per_page=max_commits, token=token)
    selected = commits[:max_commits]
    details: List[Dict] = []

    for idx, item in enumerate(selected):
        sha = item.get("sha")
        if not sha:
            continue

        detail = get_commit_detail(owner, repo, sha, token=token)
        details.append(transform_github_commit_detail(detail))

        # Respect rate limits a bit when issuing many per-commit detail requests.
        if len(selected) > 20 and idx < len(selected) - 1:
            time.sleep(0.1)

    return details
