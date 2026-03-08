"""Query-driven analyzer orchestration with session persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
import json

from core.embeddings import EmbeddingEngine, build_commit_semantic_text, rank_commits_by_semantic
from core.summarizer import CommitSummarizer
from core.vector_store import LocalVectorStore
from .query_utils import (
    candidate_commit_scores,
    fetch_diffs_for_commits,
    ingest_light,
    load_commits_metadata,
    save_commits_metadata,
)


class QueryDrivenAnalyzer:
    """Indexes commit metadata and answers focused history questions."""

    def __init__(
        self,
        repo_path: str,
        groq_api_key: Optional[str] = None,
        use_embeddings: bool = True,
        embedding_model: str = "all-MiniLM-L6-v2",
        session_dir: Optional[str] = None,
    ):
        self.repo_path = repo_path
        self.commits_index: List[Dict] = []
        self.summarizer = CommitSummarizer(api_key=groq_api_key)
        self.summary_cache: Dict[str, Dict] = {}
        self.use_embeddings = use_embeddings
        self.embedding_model = embedding_model
        self.embedding_engine: Optional[EmbeddingEngine] = None
        self.commit_embeddings: List[List[float]] = []
        self.session_dir = session_dir or Path(".") / ".git_arch_sessions" / "default"
        self.vector_store: Optional[LocalVectorStore] = None

    def index_repository(self, max_commits: Optional[int] = None, save_to_disk: bool = True) -> Dict:
        print(f"Indexing repository: {self.repo_path}")
        self.commits_index = ingest_light(self.repo_path, max_commits or 1000)

        if self.use_embeddings and self.commits_index:
            try:
                print(f"Building embeddings using model: {self.embedding_model}")
                self.embedding_engine = EmbeddingEngine(self.embedding_model)
                commit_texts = [build_commit_semantic_text(commit) for commit in self.commits_index]
                self.commit_embeddings = self.embedding_engine.encode_texts(commit_texts)
                print(f"Built embeddings for {len(self.commit_embeddings)} commits")

                if save_to_disk:
                    self._build_and_save_vector_store()
            except Exception as exc:
                self.embedding_engine = None
                self.commit_embeddings = []
                print(f"Embeddings unavailable; using heuristic retrieval: {exc}")

        stats = {
            "total_commits": len(self.commits_index),
            "date_range": {
                "oldest": self.commits_index[-1]["date"] if self.commits_index else None,
                "newest": self.commits_index[0]["date"] if self.commits_index else None,
            },
            "total_files": sum(len(commit.get("files", [])) for commit in self.commits_index),
        }

        print(f"Indexed {stats['total_commits']} commits")
        return stats

    def _build_and_save_vector_store(self) -> None:
        if not self.commit_embeddings or not self.commits_index:
            return

        self.vector_store = LocalVectorStore(dimension=len(self.commit_embeddings[0]))
        metadata = {commit["hash"]: commit for commit in self.commits_index}
        self.vector_store.add_embeddings(self.commit_embeddings, metadata)
        self.vector_store.save(str(self.session_dir))
        print(f"Saved vector store to {self.session_dir}")

    def _retrieve_candidates(self, query: str, analyze_candidates: int) -> List[Dict]:
        heuristic_scores = candidate_commit_scores(query, self.commits_index)
        by_hash = {commit["hash"]: commit for commit in self.commits_index}

        semantic_scores: Dict[str, float] = {}

        if self.vector_store and self.embedding_engine:
            try:
                query_embedding = self.embedding_engine.encode_texts([query])[0]
                vector_results = self.vector_store.search(
                    query_embedding,
                    top_k=min(len(self.commits_index), max(analyze_candidates * 3, 30)),
                )
                for index, (commit_hash, _similarity, _meta) in enumerate(vector_results):
                    semantic_scores[commit_hash] = 1.0 - (index / max(1, len(vector_results) - 1))
            except Exception as exc:
                print(f"Vector store search failed: {exc}")

        if not semantic_scores and self.embedding_engine and self.commit_embeddings:
            semantic_ranked = rank_commits_by_semantic(
                query,
                self.commits_index,
                self.commit_embeddings,
                self.embedding_engine,
                top_n=min(len(self.commits_index), max(analyze_candidates * 3, 30)),
            )
            total = max(1, len(semantic_ranked) - 1)
            for index, commit in enumerate(semantic_ranked):
                semantic_scores[commit["hash"]] = 1.0 - (index / total)

        combined = []
        all_hashes = set(heuristic_scores) | set(semantic_scores)
        for commit_hash in all_hashes:
            score = 0.45 * heuristic_scores.get(commit_hash, 0.0) + 0.55 * semantic_scores.get(commit_hash, 0.0)
            commit = by_hash.get(commit_hash)
            if commit:
                combined.append((score, commit))

        combined.sort(key=lambda item: item[0], reverse=True)
        return [commit for _, commit in combined[:analyze_candidates]]

    def answer_question(self, query: str, top_k: int = 5, analyze_candidates: int = 20) -> List[Dict]:
        if not self.commits_index:
            raise ValueError("Repository not indexed. Call index_repository() first.")

        print(f"\nQuestion: {query}")
        candidates = self._retrieve_candidates(query, analyze_candidates)
        print(f"Retrieved {len(candidates)} candidate commits")

        candidate_hashes = [commit["hash"] for commit in candidates]
        commits_with_diffs = fetch_diffs_for_commits(self.repo_path, candidate_hashes)
        commits_by_hash = {commit["hash"]: commit for commit in commits_with_diffs}

        analyzed = []
        for index, commit_meta in enumerate(candidates[:analyze_candidates], 1):
            commit_hash = commit_meta["hash"]

            if commit_hash in self.summary_cache:
                analyzed.append(self.summary_cache[commit_hash])
                continue

            if commit_hash not in commits_by_hash:
                continue

            commit_data = commits_by_hash[commit_hash]
            print(f"[{index}/{len(candidates)}] Summarizing {commit_hash[:8]} - {commit_data['message'][:60]}")
            summary = self.summarizer.summarize_commit(commit_data)
            self.summary_cache[commit_hash] = summary
            analyzed.append(summary)

        successful = [item for item in analyzed if item.get("status") == "success"]
        return successful[:top_k]

    def save_index(self, output_file: str) -> None:
        save_commits_metadata(self.commits_index, output_file)
        print(f"Saved index to {output_file}")

    def load_index(self, input_file: str) -> None:
        self.commits_index = load_commits_metadata(input_file)
        print(f"Loaded index: {len(self.commits_index)} commits")

    def save_cache(self, output_file: str) -> None:
        with open(output_file, "w") as handle:
            json.dump(self.summary_cache, handle, indent=2)
        print(f"Saved summary cache to {output_file}")

    def load_cache(self, input_file: str) -> None:
        try:
            with open(input_file, "r") as handle:
                self.summary_cache = json.load(handle)
            print(f"Loaded cache: {len(self.summary_cache)} summaries")
        except FileNotFoundError:
            print("No cache file found, starting fresh")

    def save_session(self) -> None:
        print(f"Saving session to {self.session_dir}")
        self.save_index(str(Path(self.session_dir) / "index.json"))
        self.save_cache(str(Path(self.session_dir) / "cache.json"))
        print("Session saved")

    def load_session(self) -> bool:
        session_path = Path(self.session_dir)
        if not session_path.exists():
            print(f"Session not found at {self.session_dir}")
            return False

        try:
            print(f"Loading session from {self.session_dir}")
            self.load_index(str(session_path / "index.json"))
            self.load_cache(str(session_path / "cache.json"))

            if self.use_embeddings:
                try:
                    self.vector_store = LocalVectorStore()
                    self.vector_store.load(str(self.session_dir))
                    print(f"Loaded vector store with {self.vector_store.size()} embeddings")
                except Exception as exc:
                    print(f"Could not load vector store: {exc}")

            return True
        except Exception as exc:
            print(f"Failed to load session: {exc}")
            return False


def run_cli() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("repo", help="Path to local repo")
    parser.add_argument("--query", default="", help="Query to search commits")
    parser.add_argument("--max", type=int, default=500, help="Max commits to index")
    parser.add_argument("--no-embeddings", action="store_true", help="Disable local semantic retrieval")
    parser.add_argument("--embedding-model", default="all-MiniLM-L6-v2", help="Sentence-transformers model name")
    parser.add_argument("--session-dir", default=None, help="Session directory for persistence")
    parser.add_argument("--load-session", action="store_true", help="Load session from disk (skip indexing)")
    args = parser.parse_args()

    analyzer = QueryDrivenAnalyzer(
        args.repo,
        use_embeddings=not args.no_embeddings,
        embedding_model=args.embedding_model,
        session_dir=args.session_dir,
    )

    if args.load_session:
        if not analyzer.load_session():
            print("Session load failed; re-indexing")
            analyzer.index_repository(max_commits=args.max)
    else:
        analyzer.index_repository(max_commits=args.max)
        if args.session_dir:
            analyzer.save_session()

    if args.query:
        results = analyzer.answer_question(args.query, top_k=5, analyze_candidates=20)
        print("\nTop results:")
        for result in results:
            print(result["hash"][:8], result["summary"])


if __name__ == "__main__":
    run_cli()
