"""
Lightweight Commit Indexer - Fast metadata extraction without full diffs.
Optimized for query-driven analysis: index quickly, analyze later.
"""

from pathlib import Path
from pydriller import Repository
from datetime import datetime


def index_commits_lightweight(repo_path: str, max_commits: int = None) -> list[dict]:
    """
    Extract lightweight commit metadata for fast indexing.
    
    This does NOT extract full diffs - only metadata needed for candidate selection:
    - Commit hash, message, author, date
    - List of files changed (names only, no diffs)
    - Change counts (additions/deletions)
    
    Full diffs are loaded lazily only for selected commits during retrieval.
    
    Args:
        repo_path: Absolute path to the Git repository
        max_commits: Number of commits to extract. None = all commits
    
    Returns:
        List of lightweight commit metadata dicts
    """
    commits_index = []
    repo = Repository(repo_path)
    
    for idx, commit in enumerate(repo.traverse_commits()):
        if max_commits and idx >= max_commits:
            break
        
        # Extract only file names and change counts (no diffs)
        files_touched = []
        for modified_file in commit.modified_files:
            files_touched.append({
                "filename": modified_file.filename,
                "change_type": modified_file.change_type.name,
                "additions": modified_file.added_lines,
                "deletions": modified_file.deleted_lines,
                # Note: No 'diff' field - saves memory and time
            })
        
        # Build lightweight index entry
        commit_metadata = {
            "hash": commit.hash,
            "short_hash": commit.hash[:8],
            "message": commit.msg,
            "author": commit.author.name,
            "author_email": commit.author.email,
            "date": commit.author_date.isoformat(),
            "files_touched": files_touched,
            "total_changes": sum(f["additions"] + f["deletions"] for f in files_touched),
        }
        
        commits_index.append(commit_metadata)
    
    return commits_index


def get_commit_diffs(repo_path: str, commit_hashes: list[str]) -> dict[str, dict]:
    """
    Lazily load full diffs for specific commits.
    
    Called only when commits are selected as candidates for analysis.
    
    Args:
        repo_path: Absolute path to the Git repository
        commit_hashes: List of commit hashes to load diffs for
    
    Returns:
        Dict mapping commit hash -> commit data with full diffs
    """
    commits_with_diffs = {}
    repo = Repository(repo_path)
    
    # Convert to set for faster lookup
    target_hashes = set(commit_hashes)
    
    for commit in repo.traverse_commits():
        if commit.hash not in target_hashes:
            continue
        
        # Extract full diffs only for this commit
        files_changed = []
        for modified_file in commit.modified_files:
            file_info = {
                "filename": modified_file.filename,
                "change_type": modified_file.change_type.name,
                "additions": modified_file.added_lines,
                "deletions": modified_file.deleted_lines,
                "diff": modified_file.diff or "",  # Full diff loaded here
            }
            files_changed.append(file_info)
        
        commits_with_diffs[commit.hash] = {
            "hash": commit.hash,
            "message": commit.msg,
            "author": commit.author.name,
            "author_email": commit.author.email,
            "date": commit.author_date.isoformat(),
            "files_changed": files_changed,
        }
        
        # Stop if we've found all target commits
        if len(commits_with_diffs) == len(target_hashes):
            break
    
    return commits_with_diffs
