"""
Query Analyzer - lightweight ingest and candidate retrieval

Provides:
- ingest_light: fast metadata-only commit index
- candidate_commits: rank commits for a user query
- fetch_diffs_for_commits: retrieve full diffs for selected commits
- QueryDrivenAnalyzer: orchestrator that uses the above functions

This module is self-contained and does not rely on external "indexer" or
"retrieval" modules so it is easier to test and maintain.
"""

from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import json
import re
from difflib import SequenceMatcher

from pydriller import Repository
from summarizer import CommitSummarizer
from dotenv import load_dotenv
from embeddings import EmbeddingEngine, build_commit_semantic_text, rank_commits_by_semantic
from vector_store import LocalVectorStore

# Auto-load environment variables from .env (so GROQ_API_KEY is available)
load_dotenv()


def ingest_light(repo_path: str, max_commits: int = 1000) -> List[Dict]:
    """
    Lightweight ingest: extract commit metadata without diffs.

    Returns list of dicts with: hash, message, author, date (iso), files (list)
    """
    commits = []
    repo = Repository(repo_path)

    for idx, commit in enumerate(repo.traverse_commits()):
        if idx >= max_commits:
            break

        file_list = [mf.filename for mf in commit.modified_files]

        commits.append({
            "hash": commit.hash,
            "short_hash": commit.hash[:8],
            "message": commit.msg,
            "author": commit.author.name,
            "date": commit.author_date.isoformat(),
            "files": file_list,
        })

    return commits


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", (text or "").lower())


def _message_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a or "", b or "").ratio()


def candidate_commits(query: str, commits: List[Dict], top_n: int = 20) -> List[Dict]:
    """
    Rank commits by relevance to the query.

    Scoring heuristic:
      - message similarity weight 0.6
      - filename keyword hit weight 0.3
      - recency boost weight 0.1

    Returns top_n commit dicts sorted by score (descending).
    """
    if not commits:
        return []

    # Precompute timestamps for recency
    dates = [datetime.fromisoformat(c["date"]) for c in commits]
    max_ts = max(dates).timestamp()
    min_ts = min(dates).timestamp()
    ts_range = max_ts - min_ts if max_ts != min_ts else 1.0

    q_tokens = set(_tokenize(query))

    scored = []
    for c in commits:
        msg = c.get("message", "")
        msg_score = _message_similarity(query, msg)

        # filename hit boolean
        filename_score = 0.0
        for fname in c.get("files", []):
            fname_tokens = set(_tokenize(fname))
            if q_tokens & fname_tokens:
                filename_score = 1.0
                break

        commit_ts = datetime.fromisoformat(c["date"]).timestamp()
        recency = (commit_ts - min_ts) / ts_range

        score = 0.6 * msg_score + 0.3 * filename_score + 0.1 * recency
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [c for s, c in scored[:top_n]]
    return top


def _candidate_commit_scores(query: str, commits: List[Dict]) -> Dict[str, float]:
    """
    Return heuristic retrieval scores keyed by commit hash.
    """
    if not commits:
        return {}

    dates = [datetime.fromisoformat(c["date"]) for c in commits]
    max_ts = max(dates).timestamp()
    min_ts = min(dates).timestamp()
    ts_range = max_ts - min_ts if max_ts != min_ts else 1.0

    q_tokens = set(_tokenize(query))
    scores: Dict[str, float] = {}

    for c in commits:
        msg = c.get("message", "")
        msg_score = _message_similarity(query, msg)

        filename_score = 0.0
        for fname in c.get("files", []):
            fname_tokens = set(_tokenize(fname))
            if q_tokens & fname_tokens:
                filename_score = 1.0
                break

        commit_ts = datetime.fromisoformat(c["date"]).timestamp()
        recency = (commit_ts - min_ts) / ts_range

        scores[c["hash"]] = 0.6 * msg_score + 0.3 * filename_score + 0.1 * recency

    return scores


def fetch_diffs_for_commits(repo_path: str, commit_hashes: List[str]) -> List[Dict]:
    """
    Given a list of commit hashes, return their full diffs and modified files.

    Returns list of dicts with hash, message, author, date, files_changed (incl. diff)
    """
    repo = Repository(repo_path)
    results = []
    hashes_set = set(commit_hashes)

    for commit in repo.traverse_commits():
        if commit.hash in hashes_set:
            files_changed = []
            for mf in commit.modified_files:
                files_changed.append({
                    "filename": mf.filename,
                    "change_type": mf.change_type.name,
                    "additions": mf.added_lines,
                    "deletions": mf.deleted_lines,
                    "diff": mf.diff or "",
                })

            results.append({
                "hash": commit.hash,
                "message": commit.msg,
                "author": commit.author.name,
                "date": commit.author_date.isoformat(),
                "files_changed": files_changed,
            })

            hashes_set.remove(commit.hash)
            if not hashes_set:
                break

    # return in same order as commit_hashes
    by_hash = {r["hash"]: r for r in results}
    ordered = [by_hash[h] for h in commit_hashes if h in by_hash]
    return ordered


def save_commits_metadata(commits: List[Dict], out_path: str):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(commits, f, indent=2)


def load_commits_metadata(path: str) -> List[Dict]:
    with open(path, "r") as f:
        return json.load(f)


class QueryDrivenAnalyzer:
    """
    Orchestrator for query-driven analysis using the functions in this module.

    Usage:
        analyzer = QueryDrivenAnalyzer(repo_path, groq_api_key=...)
        analyzer.index_repository(max_commits=500)
        results = analyzer.answer_question("Why was auth changed?", top_k=5)
    """

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
        """Fast indexing of repository metadata (no diffs). Optionally saves to disk."""
        print(f"📦 Indexing repository: {self.repo_path}")
        self.commits_index = ingest_light(self.repo_path, max_commits or 1000)

        if self.use_embeddings and self.commits_index:
            try:
                print(f"🧠 Building embeddings using model: {self.embedding_model}")
                self.embedding_engine = EmbeddingEngine(self.embedding_model)
                commit_texts = [build_commit_semantic_text(c) for c in self.commits_index]
                self.commit_embeddings = self.embedding_engine.encode_texts(commit_texts)
                print(f"✅ Built embeddings for {len(self.commit_embeddings)} commits")
                
                # Build and save vector store
                if save_to_disk:
                    self._build_and_save_vector_store()
            except Exception as exc:
                self.embedding_engine = None
                self.commit_embeddings = []
                print(f"⚠️  Embeddings unavailable, falling back to heuristic retrieval: {exc}")

        stats = {
            "total_commits": len(self.commits_index),
            "date_range": {
                "oldest": self.commits_index[-1]["date"] if self.commits_index else None,
                "newest": self.commits_index[0]["date"] if self.commits_index else None,
            },
            "total_files": sum(len(c.get("files", [])) for c in self.commits_index),
        }

        print(f"✅ Indexed {stats['total_commits']} commits")
        return stats

    def _build_and_save_vector_store(self) -> None:
        """Build vector store from embeddings and save to disk."""
        if not self.commit_embeddings or not self.commits_index:
            return
        
        self.vector_store = LocalVectorStore(dimension=len(self.commit_embeddings[0]))
        
        # Create metadata dict
        metadata = {c["hash"]: c for c in self.commits_index}
        
        # Add to store
        self.vector_store.add_embeddings(self.commit_embeddings, metadata)
        
        # Save to disk
        self.vector_store.save(str(self.session_dir))
        print(f"💾 Saved vector store to {self.session_dir}")

    def _retrieve_candidates(self, query: str, analyze_candidates: int) -> List[Dict]:
        """
        Hybrid retrieval: semantic ranking (via vector store if available) + heuristic ranking.
        """
        heuristic_scores = _candidate_commit_scores(query, self.commits_index)
        by_hash = {c["hash"]: c for c in self.commits_index}

        semantic_scores: Dict[str, float] = {}
        
        # Try vector store first (if loaded or available)
        if self.vector_store and self.embedding_engine:
            try:
                query_embedding = self.embedding_engine.encode_texts([query])[0]
                results = self.vector_store.search(query_embedding, top_k=min(len(self.commits_index), max(analyze_candidates * 3, 30)))
                for idx, (commit_hash, similarity, _) in enumerate(results):
                    semantic_scores[commit_hash] = 1.0 - (idx / max(1, len(results) - 1))
            except Exception as e:
                print(f"⚠️  Vector store search failed: {e}")
        
        # Fallback to in-memory semantic ranking
        if not semantic_scores and self.embedding_engine and self.commit_embeddings:
            semantic_ranked = rank_commits_by_semantic(
                query,
                self.commits_index,
                self.commit_embeddings,
                self.embedding_engine,
                top_n=min(len(self.commits_index), max(analyze_candidates * 3, 30)),
            )
            total = max(1, len(semantic_ranked) - 1)
            for idx, commit in enumerate(semantic_ranked):
                semantic_scores[commit["hash"]] = 1.0 - (idx / total)

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

        print(f"\n🔍 Question: {query}")

        # Step 1: retrieve candidate commits
        candidates = self._retrieve_candidates(query, analyze_candidates)
        print(f"   Retrieved {len(candidates)} candidate commits")

        # Step 2: fetch diffs for candidate hashes
        candidate_hashes = [c["hash"] for c in candidates]
        commits_with_diffs = fetch_diffs_for_commits(self.repo_path, candidate_hashes)
        commits_by_hash = {c["hash"]: c for c in commits_with_diffs}

        analyzed = []
        for i, c in enumerate(candidates[:analyze_candidates], 1):
            h = c["hash"]
            if h in self.summary_cache:
                analyzed.append(self.summary_cache[h])
                continue

            if h not in commits_by_hash:
                continue

            commit_data = commits_by_hash[h]
            print(f"   [{i}/{len(candidates)}] Summarizing {h[:8]} - {commit_data['message'][:60]}")
            summary = self.summarizer.summarize_commit(commit_data)
            self.summary_cache[h] = summary
            analyzed.append(summary)

        # Filter successful and return top_k
        successful = [a for a in analyzed if a.get("status") == "success"]
        return successful[:top_k]

    def save_index(self, output_file: str):
        save_commits_metadata(self.commits_index, output_file)
        print(f"💾 Saved index to {output_file}")

    def load_index(self, input_file: str):
        self.commits_index = load_commits_metadata(input_file)
        print(f"📂 Loaded index: {len(self.commits_index)} commits")

    def save_cache(self, output_file: str):
        with open(output_file, "w") as f:
            json.dump(self.summary_cache, f, indent=2)
        print(f"💾 Saved summary cache to {output_file}")

    def load_cache(self, input_file: str):
        try:
            with open(input_file, "r") as f:
                self.summary_cache = json.load(f)
            print(f"📂 Loaded cache: {len(self.summary_cache)} summaries")
        except FileNotFoundError:
            print("⚠️  No cache file found, starting fresh")
    
    def save_session(self) -> None:
        """Save entire session (index + embeddings + cache) to disk."""
        print(f"💾 Saving session to {self.session_dir}")
        self.save_index(str(Path(self.session_dir) / "index.json"))
        self.save_cache(str(Path(self.session_dir) / "cache.json"))
        print(f"✅ Session saved")
    
    def load_session(self) -> bool:
        """Load session from disk. Returns True if successful."""
        session_path = Path(self.session_dir)
        if not session_path.exists():
            print(f"⚠️  Session not found at {self.session_dir}")
            return False
        
        try:
            print(f"📂 Loading session from {self.session_dir}")
            self.load_index(str(session_path / "index.json"))
            self.load_cache(str(session_path / "cache.json"))
            
            # Load vector store if embeddings are enabled
            if self.use_embeddings:
                try:
                    self.vector_store = LocalVectorStore()
                    self.vector_store.load(str(self.session_dir))
                    print(f"✅ Loaded vector store with {self.vector_store.size()} embeddings")
                except Exception as e:
                    print(f"⚠️  Could not load vector store: {e}")
            
            return True
        except Exception as e:
            print(f"⚠️  Failed to load session: {e}")
            return False


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("repo", help="Path to local repo")
    p.add_argument("--query", default="", help="Query to search commits")
    p.add_argument("--max", type=int, default=500, help="Max commits to index")
    p.add_argument("--no-embeddings", action="store_true", help="Disable local semantic retrieval")
    p.add_argument("--embedding-model", default="all-MiniLM-L6-v2", help="Sentence-transformers model name")
    p.add_argument("--session-dir", default=None, help="Session directory for persistence")
    p.add_argument("--load-session", action="store_true", help="Load session from disk (skip indexing)")
    args = p.parse_args()

    analyzer = QueryDrivenAnalyzer(
        args.repo,
        use_embeddings=not args.no_embeddings,
        embedding_model=args.embedding_model,
        session_dir=args.session_dir,
    )
    
    # Try to load session if requested
    if args.load_session:
        if not analyzer.load_session():
            print("⚠️  Session load failed, will re-index")
            analyzer.index_repository(max_commits=args.max)
    else:
        analyzer.index_repository(max_commits=args.max)
        if args.session_dir:
            analyzer.save_session()

    if args.query:
        results = analyzer.answer_question(args.query, top_k=5, analyze_candidates=20)
        print("\nTop results:")
        for r in results:
            print(r["hash"][:8], r["summary"])
