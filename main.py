"""
Git Archaeologist - Query-Driven Commit Analysis
Indexes repos quickly, analyzes commits on-demand based on user questions.

New Architecture:
1. Lightweight indexing (one-time, fast)
2. User asks question
3. Retrieve relevant candidates
4. Analyze only those commits with LLM
5. Return ranked results
"""

import json
from pathlib import Path
from dotenv import load_dotenv

from query_analyzer import QueryDrivenAnalyzer

# Load environment variables from .env file
load_dotenv()


def demo_query_driven_analysis():
    """
    Demonstrate the new query-driven analysis workflow.
    
    Flow:
    1. Index repo (fast, one-time)
    2. Ask questions
    3. Get targeted answers
    """
    repo_path = "/Users/yanshikesharwani/vscode/Git Archaeologist"
    
    # Initialize analyzer
    analyzer = QueryDrivenAnalyzer(repo_path)
    
    # Step 1: Index repository (fast - no diffs loaded)
    print("🚀 Step 1: Indexing repository...")
    stats = analyzer.index_repository(max_commits=100)  # Or None for all commits
    
    # Save index for future use
    analyzer.save_index("repo_index.json")
    
    # Step 2: Answer questions (targeted analysis)
    print("\n🚀 Step 2: Answering questions...")
    
    # Example questions
    questions = [
        "Why was the commit extraction added?",
        "What changes were made to binary file detection?",
        "How was the main module structured?",
    ]
    
    for question in questions:
        results = analyzer.answer_question(
            query=question,
            top_k=3,  # Return top 3 results
            analyze_candidates=10  # Analyze top 10 candidates deeply
        )
        
        # Display results
        print(f"\n📋 Results for: '{question}'")
        print("-" * 60)
        for idx, result in enumerate(results, 1):
            print(f"\n{idx}. Commit {result['hash'][:8]}")
            print(f"   Message: {result['message']}")
            print(f"   Summary: {result['summary']}")
    
    # Save analysis cache
    analyzer.save_cache("summary_cache.json")


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
    
    Supports:
    - Images: PNG, JPG, GIF, ICO, WEBP
    - Media: MP3, MP4, MOV, WAV
    - Archives: ZIP, TAR, GZ, RAR
    - Compiled: PYC, SO, O, A
    - Documents: PDF, DOCX, XLS
    
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


def summarize_commits(commits: list[dict], api_key: str = None) -> list[dict]:
    """
    Generate summaries for extracted commits using Groq API.
    
    Args:
        commits: List of commits from extract_commits()
        api_key: Groq API key (optional, reads from env if None)
    
    Returns:
        List of commit summaries with AI-generated explanations
    """
    print("\n🤖 Generating AI summaries...")
    print("=" * 60)
    
    summarizer = CommitSummarizer(api_key=api_key)
    summaries = summarizer.summarize_commits_batch(commits)
    
    return summaries


def main():
    """
    Main entry point: demonstrate query-driven analysis.
    
    New workflow:
    1. Index repo quickly (metadata only)
    2. Answer user questions
    3. Analyze only relevant commits
    """
    demo_query_driven_analysis()


# # Legacy functions below (kept for backward compatibility)
# # These are no longer used in the main workflow but may be useful for testing

# from pydriller import Repository
# from summarizer import CommitSummarizer

# def extract_commits(repo_path: str, max_commits: int = 20) -> list[dict]:
