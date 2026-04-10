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

---

## Phase 3: Authentication Layer (2026-04-09)

### Step 11: Stateless JWT Authentication
- **Task:** Implement secure user authentication supporting Email/Password, GitHub OAuth, and Google OAuth.
- **Framework Chosen:** `PyJWT` for token signing, `passlib[bcrypt]` for password hashing, `authlib` for OAuth flows.
- **Reasoning:** Stateless JWTs eliminate server-side session storage entirely, allowing horizontal scaling without shared session caches. `authlib` provides a battle-tested OAuth client that handles CSRF state validation and token exchange for both GitHub and Google providers.
- **Key Decision:** Pinned `bcrypt==3.2.2` to resolve a `passlib` compatibility bug where newer bcrypt versions removed the `__about__` module attribute.

### Step 12: Frontend Auth Integration
- **Task:** Build React-side auth context, modal UI, and automatic token management.
- **Components Created:** `AuthProvider` (context + URL token interception), `AuthModal` (login/register/OAuth buttons), Axios request interceptors.
- **Framework Chosen:** `sonner` for toast notifications.
- **Reasoning:** OAuth callbacks redirect to the frontend with `?token=` query params. The `AuthProvider` intercepts this on mount, stores the JWT in `localStorage`, clears the URL, and triggers a toast — all without requiring a dedicated callback page component.
- **Key Decision:** Toast notifications were wired for all auth flows (email, Google, GitHub) including error states, ensuring users always receive visual feedback.

### Step 13: SQLAlchemy User Model & DB Auto-Provisioning
- **Task:** Define the `User` model and ensure tables are created on server boot.
- **Schema:** `id` (UUID), `email` (unique), `hashed_password` (nullable for OAuth-only users), `github_id`, `google_id`, `created_at`.
- **Reasoning:** Making `hashed_password` nullable allows OAuth-only users to exist without a password. Unique constraints on `github_id` and `google_id` prevent duplicate OAuth accounts.
- **Key Decision:** `Base.metadata.create_all()` runs on FastAPI startup, so SQLite tables are auto-provisioned without manual migration scripts during local development.

---

## Phase 4: Repository Linking & Ingestion (2026-04-09)

### Step 14: Repository, Commit, and FileDiff SQLAlchemy Models
- **Task:** Define relational models to persistently store repository metadata, commit history, and per-file diffs.
- **Schema:**
  - `Repository`: `id`, `url` (unique), `owner`, `name`, `last_indexed_commit`, `created_at`
  - `Commit`: `id`, `repository_id` (FK), `hash`, `author_name`, `author_email`, `message`, `timestamp`
  - `FileDiff`: `id`, `commit_id` (FK), `file_path`, `status` (ADD/MODIFY/DELETE), `diff_content`
- **Reasoning:** Storing raw diffs — not just commit messages — is critical for forensic AI analysis. Commit messages are often vague ("fix bug"), but the actual diff content reveals exactly what changed and why.

### Step 15: Background PyDriller Ingestion Worker
- **Task:** Asynchronously clone and parse repository history without blocking the HTTP response.
- **Framework Chosen:** FastAPI `BackgroundTasks` + `PyDriller`.
- **Reasoning:** `PyDriller` physically clones the repo and walks each commit as a Python generator, extracting parsed diffs natively. Using `BackgroundTasks` instead of Celery keeps the stack simple — the user gets an immediate `200 OK` while ingestion runs in a thread pool.
- **Key Decision:** Implemented a `last_indexed_commit` checkpoint system. On re-sync, PyDriller uses `from_commit=` to skip already-indexed history, preventing duplicate data and saving bandwidth.
- **Safety:** Diff content is capped at 15KB per file, and commits are flushed to the DB in batches of 300 to prevent memory exhaustion on large repos.

### Step 16: Frontend Repository Linker UI
- **Task:** Replace the legacy RAG query interface with a focused "Link Repository" form.
- **Changes:** Stripped out `analyzeQuery`, `indexRepository`, chat session APIs from the frontend. Replaced `SearchInterface` with a single URL input + "Link Repository" button that calls `POST /repos/link`.
- **Reasoning:** Phase 4 is strictly about ingestion — attaching the query/chat UI prematurely would create broken UX since the retrieval pipeline isn't wired to the new SQL-backed data yet.
- **Key Decision:** The results panel shows an "ACTIVE INGESTION" badge after linking, giving visual confirmation that background processing is running.

---

## Phase 5: RAG Retrieval & Answer Quality Improvements (2026-04-09)

### Step 17: Eliminating Per-Commit LLM Summarization
- **Task:** Reduce LLM API calls from ~20 per query (one per candidate commit) to exactly 1 (the final synthesis).
- **File Modified:** `analyzers/query_analyzer.py` — `answer_question()`.
- **Before:** Every candidate commit was individually sent to Groq for a 1-2 sentence summary. Most summaries were discarded (only top 5 used).
- **After:** Raw diff data is passed directly through the pipeline. Cached summaries are used if available, but no new per-commit LLM calls are made. The single synthesis call handles everything.
- **Reasoning:** 20 sequential Groq calls cost ~4-8 seconds and burn API quota. The summaries were "lossy" — they compressed rich diff data into 1-2 sentences, destroying the very code-level context the user needs.

### Step 18: Feeding Raw Diffs Into Synthesis
- **Task:** Give the final answer-generation LLM actual code changes, not just commit message + summary.
- **Files Modified:** `pipelines/rag_pipeline.py` (synthesis prompt), `pipelines/rag_models.py` (added `diff_snippets`, `files_changed` fields), `analyzers/query_analyzer.py` (builds diff snippets from `files_changed` data).
- **Reasoning:** The original pipeline committed "evidence starvation" — the synthesis LLM only saw `commit_hash | date | message + summary`. It never saw the actual added/removed code lines. Now each evidence block includes truncated raw diffs (up to 3KB per commit), letting the LLM cite specific functions, imports, and patterns.

### Step 19: Conversational Prompt Rewrite
- **Task:** Replace rigid numbered-list template with a natural, evidence-grounded conversational prompt.
- **File Modified:** `pipelines/rag_pipeline.py` — `synthesize_answer()`.
- **Before:** Hardcoded `1) Direct answer 2) Key evidence 3) Why this happened` structure. Mechanical "Confidence (deterministic)" footer appended to every answer.
- **After:** System prompt identifies as "Git Archaeologist" and instructs the model to cite commits inline, reference code, write naturally, and avoid rigid formatting. Confidence metadata is computed but no longer appended to the answer text.
- **Key Decision:** Added `_call_groq_synthesis()` to `core/summarizer.py` using proper `system`/`user` message roles and `max_tokens=1000` (vs. 200 for per-commit summaries).

### Step 20: Multi-Turn Conversation Support
- **Task:** Enable follow-up questions that reference prior context.
- **File Modified:** `pipelines/rag_pipeline.py` — `synthesize_answer()` now accepts optional `conversation_history: List[Dict]`.
- **Reasoning:** Without conversation history, questions like "who else worked on that?" fail completely because "that" has no referent. The last 6 turns are injected as `ROLE: content` context blocks before the current question.

### Step 21: Heuristic Retrieval Rebalancing
- **Task:** Reduce commit-message bias in candidate scoring.
- **File Modified:** `analyzers/query_utils.py` — `candidate_commit_scores()`.
- **Before:** `message_similarity=60%, filename_score=30%, recency=10%`.
- **After:** `message_similarity=35%, filename_score=40%, recency=25%`.
- **Reasoning:** Commits with terse messages like "fix" or "wip" were systematically buried even when their diffs contained exactly what the user asked about. Increasing filename weight surfaces commits touching relevant files, and recency gives appropriate weight to recent changes.

### Step 22: Adaptive Diff Budget With Full File Coverage
- **Task:** Replace hard file/line caps with an intelligent per-commit character budget that includes ALL modified files.
- **File Modified:** `analyzers/query_analyzer.py` — diff construction inside `answer_question()`.
- **Before:** Hard limit of 5 files × 50 lines. File #6+ was completely invisible. No query-awareness in file ordering.
- **After:** Uses a 6000-character budget per commit. Files are sorted by query relevance (filename token overlap) and change size. Query-relevant files get full filtered diffs first. Remaining files fill the leftover budget. Files that exceed the budget get a compact one-line summary (filename, change type, +/- counts), so the LLM still knows *every* file that was touched.
- **Reasoning:** A commit modifying 15 files shouldn't have 10 of them invisible. The budget approach ensures the most forensically valuable code fills the context window, while every file still appears at minimum as a compact reference. The system now adapts: a commit with 3 large files uses the full budget on them, while a commit with 20 small files fits all of them.

---

## Phase 6: Persistent Chat Sessions & Conversation Memory (2026-04-09)

### Step 23: SQLAlchemy Chat Models
- **Task:** Implement database storage for chat sessions and messages.
- **File Modified:** `db/models.py`.
- **Changes:** Added `ChatSession` (linked to `User` and optionally `Repository`) and `ChatMessage` (role, content, timestamp). Removed the legacy Postgres-only dict-based chat store.

### Step 24: Rewriting Chat Routes
- **Task:** Rebuild the `/chat` API endpoints using FastAPI + SQLAlchemy.
- **File Modified:** `api/routes/chat.py`.
- **Changes:** 
  - All endpoints are now user-scoped (requires JWT).
  - Implemented `POST /chat/sessions`, `GET /chat/sessions`, and `GET /chat/sessions/{id}`.
  - The core endpoint `POST /chat/sessions/{id}/messages` now: (1) saves the user message, (2) loads the last 10 messages as `conversation_history`, (3) runs the full RAG pipeline, and (4) saves the generated assistant message.

### Step 25: Frontend Chat Interface
- **Task:** Build the chat UI and wire it into the main layout.
- **Files Modified:** `frontend/components/ChatPanel.tsx`, `frontend/components/ScanHistory.tsx`, `frontend/app/page.tsx`.
- **Changes:** 
  - Created `ChatPanel` with Markdown, GFM, and Prism syntax highlighting support.
  - Handles optimistic UI updates and auto-scrolls on new messages.
  - Refactored `ScanHistory` to display real `ChatSessionItem`s fetched from the DB instead of mock data. The UI now splits the screen between the repo linker and the active chat thread.

### Step 26: Fix RAG Pipeline — DB-Loaded Commits Contain Diffs
- **Task:** Fix `'dict' object has no attribute 'lower'` crash in the RAG pipeline.
- **Files Modified:** `analyzers/query_utils.py`, `analyzers/query_analyzer.py`.
- **Root Cause:** Commits loaded from SQLAlchemy had `files` as `[{filename, status, diff, ...}]` (dicts), but `candidate_commit_scores()` and `answer_question()` assumed they were plain strings. Additionally, `fetch_diffs_for_commits()` tried to re-fetch from the GitHub API even though diffs were already in memory.
- **Fix:** 
  - `query_utils.py`: `candidate_commit_scores()` now handles both dict and string file entries.
  - `query_analyzer.py`: `answer_question()` detects when commits already carry diff data and reformats them in-place, skipping the redundant API call entirely.
  - Removed dead `index_store` and `summary_store` references from the legacy pgvector stores.

### Step 27: Wire load_session() Into Chat Route
- **Task:** Ensure the analyzer actually loads commits from the DB before the RAG pipeline runs.
- **File Modified:** `api/routes/chat.py`.
- **Change:** Added `analyzer.load_session()` call when `commits_index` is empty, so the pipeline hydrates from SQLAlchemy before retrieval. Also removed the `VECTOR_BACKEND == "pgvector"` gate from `load_session()` since all GitHub repos should load from the DB regardless of vector store backend.

### Step 28: Activate Semantic Embeddings for DB-Loaded Repos
- **Task:** Fix dead semantic scoring path — embeddings were never built for repos loaded from the DB.
- **File Modified:** `analyzers/query_analyzer.py` — `load_session()`.
- **Before:** After loading commits from PostgreSQL, the code tried to load a pre-built vector store from disk. Since one never existed, it printed "0 embeddings" and continued with heuristic-only retrieval. The `0.55 * semantic` weight in `_retrieve_candidates()` was contributing nothing.
- **After:** If the vector store is empty or missing, `load_session()` now builds embeddings on the fly using `EmbeddingEngine` + `build_commit_semantic_text()`, then saves the vector store to disk for future reuse. First query incurs a one-time ~2-5 second encoding cost; subsequent queries are instant.
- **Impact on responses:** With semantic scoring active, the retrieval pipeline can now surface commits even when query keywords don't match the commit message. For example, asking "how was real-time communication added?" can now match a commit with message "add socket.io chat feature" because the sentence-transformer understands semantic similarity. This should noticeably improve answer quality for conceptual/abstract questions.
