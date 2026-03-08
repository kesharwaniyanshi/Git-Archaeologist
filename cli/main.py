"""CLI demo entrypoint for query-driven Git Archaeologist workflows."""

from __future__ import annotations

from dotenv import load_dotenv

from analyzers.query_analyzer import QueryDrivenAnalyzer

load_dotenv()


def demo_query_driven_analysis(repo_path: str, max_commits: int = 100) -> None:
    """Run a lightweight demo that indexes and answers sample questions."""
    analyzer = QueryDrivenAnalyzer(repo_path)

    print("Step 1: Indexing repository...")
    analyzer.index_repository(max_commits=max_commits)
    analyzer.save_index("repo_index.json")

    print("\nStep 2: Answering questions...")
    questions = [
        "Why was the commit extraction added?",
        "What changes were made to binary file detection?",
        "How was the main module structured?",
    ]

    for question in questions:
        results = analyzer.answer_question(query=question, top_k=3, analyze_candidates=10)
        print(f"\nResults for: '{question}'")
        print("-" * 60)
        for index, result in enumerate(results, 1):
            print(f"\n{index}. Commit {result['hash'][:8]}")
            print(f"   Message: {result['message']}")
            print(f"   Summary: {result['summary']}")

    analyzer.save_cache("summary_cache.json")


def main() -> None:
    repo_path = "/Users/yanshikesharwani/vscode/Git Archaeologist"
    demo_query_driven_analysis(repo_path)


if __name__ == "__main__":
    main()
