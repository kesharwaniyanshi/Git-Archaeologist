# Git Archaeologist - Development & Decision Log

## Overview
This document serves as the chronological step-by-step development log and Architecture Decision Record (ADR) for Git Archaeologist. It tracks every major operational phase, outlining the "Why" behind fundamental framework choices, models, and implementation structures. 

*Whenever new components and features are introduced via tasks, this document must be appended with the exact reasoning for why the technical pathway was chosen.*

---

## Phase 1: Prototype Ingestion and Subsystem Builds (Legacy Phase)

### Step 1: Git Commit Extraction
- **Task:** Extract raw git metadata and diffs without halting system memory.
- **Framework Chosen:** `PyDriller` (Python).
- **Reasoning:** `GitPython` relies heavily on system OS processes which can bottleneck memory on large repos. PyDriller provides a cleaner, highly-optimized generator-based API for parsing full unified diffs programmatically, which is essential for LLM ingestion.
- **Key Decision:** Removed natively binary strings/images from extraction to save LLM prompt tokens and database space.

### Step 2: AI Summarization 
- **Task:** Transform raw code diffs into human-readable semantic context.
- **Model Chosen:** `llama-3.3-70b` via Groq API.
- **Reasoning:** Strict requirement for 100% free-tier architecture. Groq provides ultra-low latency inference globally, which helps bypass the severe bottlenecks of sequential diff-summarization.
- **Engineering Strategy:** Truncated large diffs (maxing at the first 50 lines) and synthetically extracted dependency python imports to save LLM tokens while maintaining coding intent accuracy.

### Step 3 & 4: Initial Vector Storage & Embeddings 
- **Task:** Convert translated text into semantic vectors and persist them locally.
- **Model Chosen:** `sentence-transformers` (`all-MiniLM-L6-v2`) generating 384-dimensional vectors.
- **Reasoning:** Lightweight local embedding model that runs entirely on free CPU allocations, highly proven for short-to-medium length queries.
- **DB Chosen (Prototype):** FAISS (Facebook AI Similarity Search) backing up `.index` and `.json` files locally to `.git_arch_sessions/`.
- **Reasoning:** Allowed for rapid initial prototyping completely offline. 
- **Flaw Identified:** Mutating local file system indices caused major concurrency read locks when shifting the prototype onto the FastAPI server, preventing multi-tenant scaling. 

### Step 5 & 6: Prototype RAG FastAPI Server 
- **Task:** Accept remote queries and execute retrieval searches.
- **Framework Chosen:** FastAPI.
- **Reasoning:** Best-in-class asynchronous IO support in Python. Standard synchronous frameworks (like Flask) would lock the event loop during heavy FAISS memory calculations, halting other users.
- **Ranking Strategy:** "Hybrid Retrieval". Combines semantic vector ranking (55% weight) with chronological/keyword heuristic scoring (45%). This is critical because it prevents hyper-relevant but ancient commits from dominating recent, mildly-similar bug fixes.

---

## Phase 2: Production Architecture Refactor (Current Era)

### Step 7: Shifting to Clean MVC & Service Architecture
- **Task:** Dismantle monolithic "God Classes" (like `QueryDrivenAnalyzer`) and monolithic single-file routing APIs (`api/app.py`).
- **Structure Chosen:** Service-Controller pattern with distinct hierarchical folders: `/routes`, `/services`, `/models`, and `dependencies.py`.
- **Reasoning:** The initial prototype intertwined database management, LLM calls, and API responses all sequentially. By separating into `/routes` and `/core/services`, we natively isolate business logic. This prepares the system to attach async `Celery` background ingestion tasks safely.

### Step 8: Standardizing Pydantic API Validations
- **Task:** Extract and lock all API validation requests.
- **Framework Chosen:** Pydantic Models (`core/models/api.py`).
- **Reasoning:** Thwarts arbitrary payload injections and OS Path Traversal hacking attempts strictly on `repo_url` routes by shifting JSON coercion to Python's C-compiled validation system bound to FastAPI.

### Step 9: Implementing Structured Logging
- **Task:** Eradicate raw `print()` statements lacking context.
- **Framework Chosen:** `structlog`.
- **Reasoning:** Standard debug logging loses thread safety and tracing metadata quickly. `structlog` automatically enforces JSON-formatted trace outputs (injecting environment and timestamp variables). Absolute necessity for observability when advancing to production environments like Vercel or AWS Cloudwatch logs.

### Step 10: PostgreSQL and pgvector Migration Strategy
- **Task:** Permanently replace local disk-based FAISS with a persistent cloud SQL DB.
- **Framework Chosen:** PostgreSQL + `pgvector`. (Neon Cloud recommended due to psycopg compatibility).
- **Reasoning:** FAISS lacks native relational constraints (e.g., retrieving embeddings *only* for User X's repositories). Migrating entirely to Postgres allows us to combine User OAuth tracking natively with `HNSW` vector-cosine indices on the same hardware.
