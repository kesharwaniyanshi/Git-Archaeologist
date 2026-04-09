from typing import Dict, Optional
from analyzers.query_analyzer import QueryDrivenAnalyzer

class AnalyzerHandle:
    def __init__(self, key: str, analyzer: QueryDrivenAnalyzer):
        self.key = key
        self.analyzer = analyzer

class AnalyzerRegistry:
    def __init__(self):
        self._handles: Dict[str, AnalyzerHandle] = {}

    @staticmethod
    def _key(repo_path: str, session_dir: Optional[str], embedding_model: str, use_embeddings: bool) -> str:
        return "|".join([
            repo_path,
            session_dir or ".git_arch_sessions/default",
            embedding_model,
            str(use_embeddings),
        ])

    def get_or_create(
        self,
        repo_path: str,
        session_dir: Optional[str],
        use_embeddings: bool,
        embedding_model: str,
    ) -> QueryDrivenAnalyzer:
        key = self._key(repo_path, session_dir, embedding_model, use_embeddings)

        if key in self._handles:
            return self._handles[key].analyzer

        analyzer = QueryDrivenAnalyzer(
            repo_path=repo_path,
            use_embeddings=use_embeddings,
            embedding_model=embedding_model,
            session_dir=session_dir,
        )
        self._handles[key] = AnalyzerHandle(key=key, analyzer=analyzer)
        return analyzer

    def status(self) -> Dict:
        sessions = []
        for key, handle in self._handles.items():
            sessions.append(
                {
                    "key": key,
                    "repo_path": handle.analyzer.repo_path,
                    "session_dir": str(handle.analyzer.session_dir),
                    "indexed_commits": len(handle.analyzer.commits_index),
                    "cached_summaries": len(handle.analyzer.summary_cache),
                    "embeddings_enabled": handle.analyzer.use_embeddings,
                }
            )
        return {"active_sessions": len(sessions), "sessions": sessions}

# Global registry instance
analyzer_registry = AnalyzerRegistry()

def get_registry() -> AnalyzerRegistry:
    return analyzer_registry
