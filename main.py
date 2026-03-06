"""
Git Archaeologist - Step 1: Commit Extraction
Extracts the last N commits from a local Git repository with full diff information.
"""

import json
from pathlib import Path
from pydriller import Repository


def extract_commits(repo_path: str, max_commits: int = 20) -> list[dict]:
    """
    Extract commits from a local Git repository.
    
    Args:
        repo_path: Absolute path to the Git repository
        max_commits: Number of commits to extract (most recent first)
    
    Returns:
        List of commit dictionaries with hash, message, author, date, and file changes
    """
    commits_data = []
    
    # PyDriller traverses commits in reverse chronological order by default
    repo = Repository(repo_path)
    
    for idx, commit in enumerate(repo.traverse_commits()):
        # Stop after max_commits
        if idx >= max_commits:
            break
        
        # Extract file changes for this commit
        files_changed = []
        
        for modified_file in commit.modified_files:
            # Skip binary files (no readable diff)
            if _is_binary(modified_file.filename):
                continue
            
            file_info = {
                "filename": modified_file.filename,
                "change_type": modified_file.change_type.name,  # ADD, MODIFY, DELETE, RENAME
                "additions": modified_file.added_lines,
                "deletions": modified_file.deleted_lines,
                "diff": modified_file.diff or "",  # Empty string if no diff available
            }
            files_changed.append(file_info)
        
        # Build commit record
        commit_record = {
            "hash": commit.hash,
            "message": commit.msg,
            "author": commit.author.name,
            "author_email": commit.author.email,
            "date": commit.author_date.isoformat(),
            "files_changed": files_changed,
        }
        
        commits_data.append(commit_record)
    
    return commits_data


def _is_binary(filename: str) -> bool:
    """
    Check if a file is likely binary based on extension.
    
    Args:
        filename: Path to the file
    
    Returns:
        True if file appears to be binary, False otherwise
    """
    binary_extensions = {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp",  # Images
        ".mp3", ".mp4", ".mov", ".wav",                     # Media
        ".zip", ".tar", ".gz", ".rar",                      # Archives
        ".pyc", ".pyo", ".so", ".o", ".a",                  # Compiled
        ".pdf", ".doc", ".docx", ".xls",                    # Documents
    }
    
    file_path = Path(filename)
    return file_path.suffix.lower() in binary_extensions


def main():
    """
    Main entry point: extract commits and print as JSON.
    """
    # For now, hardcode the repo path. You'll make this a CLI arg later.
    repo_path = "/Users/yanshikesharwani/vscode/Git Archaeologist"
    
    print(f"📦 Extracting commits from: {repo_path}")
    print("=" * 60)
    
    commits = extract_commits(repo_path, max_commits=20)
    
    print(f"✅ Extracted {len(commits)} commits\n")
    
    # Pretty-print the JSON
    print(json.dumps(commits, indent=2))
    
    # Optional: Save to file
    output_file = "commits_extracted.json"
    with open(output_file, "w") as f:
        json.dump(commits, f, indent=2)
    print(f"\n💾 Saved to {output_file}")


if __name__ == "__main__":
    main()
