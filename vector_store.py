"""
Local Vector Store - persistent embeddings and metadata storage.

Uses FAISS for fast similarity search and JSON for metadata.
Provides session save/load for reproducible queries across runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


class LocalVectorStore:
    """
    Persistent vector store using FAISS for similarity search.
    
    Stores:
    - Embeddings in FAISS index (binary, fast search)
    - Metadata in JSON (commit hash, message, files, date)
    - Mappings between index position and commit hash
    """
    
    def __init__(self, dimension: int = 384):
        """
        Initialize vector store.
        
        Args:
            dimension: Vector embedding dimension (384 for all-MiniLM-L6-v2)
        """
        try:
            import faiss
        except ImportError as exc:
            raise ImportError(
                "faiss-cpu is not installed. Run: pip install faiss-cpu"
            ) from exc
        
        self.faiss = faiss
        self.dimension = dimension
        self.index = self.faiss.IndexFlatIP(dimension)  # IP = inner product (cosine for normalized)
        self.metadata: Dict[str, Dict] = {}  # hash -> commit metadata
        self.hash_to_position: Dict[str, int] = {}  # hash -> FAISS index position
        self.position_to_hash: Dict[int, str] = {}  # FAISS index position -> hash
    
    def add_embeddings(
        self,
        embeddings: List[List[float]],
        metadata: Dict[str, Dict],
    ) -> None:
        """
        Add embeddings and metadata to the store.
        
        Args:
            embeddings: List of embedding vectors (should be normalized for cosine)
            metadata: Dict mapping commit hash -> commit data
        """
        if not embeddings or not metadata:
            return
        
        # Convert to numpy array for FAISS
        vectors = np.array(embeddings, dtype=np.float32)
        
        # Add to index
        start_position = self.index.ntotal
        self.index.add(vectors)
        
        # Track mappings
        for idx, (commit_hash, commit_meta) in enumerate(metadata.items()):
            position = start_position + idx
            self.hash_to_position[commit_hash] = position
            self.position_to_hash[position] = commit_hash
            self.metadata[commit_hash] = commit_meta
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 20,
    ) -> List[Tuple[str, float, Dict]]:
        """
        Retrieve top-k commits by similarity to query embedding.
        
        Args:
            query_embedding: Query vector (should be normalized)
            top_k: Number of results to return
        
        Returns:
            List of (commit_hash, similarity_score, metadata) tuples
        """
        if self.index.ntotal == 0:
            return []
        
        query = np.array([query_embedding], dtype=np.float32)
        distances, indices = self.index.search(query, min(top_k, self.index.ntotal))
        
        results = []
        for distance, idx in zip(distances[0], indices[0]):
            if idx >= 0:  # Valid result
                commit_hash = self.position_to_hash.get(int(idx))
                if commit_hash and commit_hash in self.metadata:
                    results.append((
                        commit_hash,
                        float(distance),
                        self.metadata[commit_hash],
                    ))
        
        return results
    
    def save(self, save_dir: str) -> None:
        """
        Save index and metadata to disk.
        
        Args:
            save_dir: Directory to save files (created if needed)
        """
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        
        # Save FAISS index
        self.faiss.write_index(self.index, str(save_path / "faiss.index"))
        
        # Save metadata
        metadata_file = save_path / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(self.metadata, f, indent=2)
        
        # Save hash mappings
        mappings_file = save_path / "mappings.json"
        with open(mappings_file, "w") as f:
            json.dump({
                "hash_to_position": self.hash_to_position,
                "position_to_hash": {int(k): v for k, v in self.position_to_hash.items()},
            }, f, indent=2)
    
    def load(self, load_dir: str) -> None:
        """
        Load index and metadata from disk.
        
        Args:
            load_dir: Directory containing saved files
        """
        load_path = Path(load_dir)
        
        # Load FAISS index
        index_file = load_path / "faiss.index"
        if index_file.exists():
            self.index = self.faiss.read_index(str(index_file))
        
        # Load metadata
        metadata_file = load_path / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, "r") as f:
                self.metadata = json.load(f)
        
        # Load mappings
        mappings_file = load_path / "mappings.json"
        if mappings_file.exists():
            with open(mappings_file, "r") as f:
                mappings = json.load(f)
                self.hash_to_position = mappings.get("hash_to_position", {})
                self.position_to_hash = {
                    int(k): v for k, v in mappings.get("position_to_hash", {}).items()
                }
    
    def size(self) -> int:
        """Return number of embeddings in the store."""
        return self.index.ntotal if self.index else 0
    
    def clear(self) -> None:
        """Clear all embeddings and metadata."""
        self.index = self.faiss.IndexFlatIP(self.dimension)
        self.metadata = {}
        self.hash_to_position = {}
        self.position_to_hash = {}
